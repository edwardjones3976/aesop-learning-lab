"""AST-based structural similarity guard for held-out evaluation items.

Computes a code-shape signature for items and lessons, ignoring variable names
and literal values, to detect when held-out items share structural shapes with
studied items or lesson code examples.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


def extract_code_snippets_from_pack(pack_data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Extract held-out items and learner-visible source code snippets from a pack dictionary.

    Returns:
        (held_out_items, learner_visible_sources)
        Each item is a dict with keys: 'id', 'family_id', 'body', 'source_type'.
    """
    held_out: List[Dict[str, Any]] = []
    sources: List[Dict[str, Any]] = []

    for item in pack_data.get("items", []):
        body = item.get("body", "")
        entry = {
            "id": item.get("id"),
            "family_id": item.get("family_id"),
            "body": body,
            "source_type": "item",
        }
        if item.get("held_out"):
            held_out.append(entry)
        else:
            if body.strip():
                sources.append(entry)

    for lesson in pack_data.get("lessons", []):
        body = lesson.get("body", "")
        fences = re.findall(r"```python\s*(.*?)```", body, re.DOTALL)
        for idx, code in enumerate(fences):
            if code.strip():
                sources.append({
                    "id": f"{lesson.get('id')}_fence_{idx}",
                    "family_id": lesson.get("id"),
                    "body": code,
                    "source_type": "lesson_code_block",
                })

    return held_out, sources


def compute_code_signature(code_str: str) -> Tuple[Any, ...]:
    """Compute an AST code-shape signature for a code snippet.

    For snippets with recursive functions:
      - Parameter count
      - How self-call changes arguments (minus_constant, plus_constant, integer_halving, slicing, unchanged)
      - Base-case test shape (eq_zero, lt_or_lte_constant, gt_or_gte_param, gt_or_gte_constant, length_test)
      - Recursive return action with self-call result:
        - string concatenation (string_concat)
        - numeric + (numeric_add) or * (numeric_mult)
        - pass-through (pass_through)

    For snippets with non-recursive functions:
      - Function count (via outer tuple length)
      - Parameter count
      - Default argument count
      - Return expression shape (e.g. BinOp_Mult, BinOp_Add, Constant_int, Name, Call)

    Names and literals are ignored.
    """
    code_str = code_str.strip()
    if not code_str:
        return ("empty",)

    try:
        tree = ast.parse(code_str)
    except Exception:
        return ("unparseable",)

    fns = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    if not fns:
        return ("no_functions",)

    fn_sigs = []
    for fn in fns:
        param_names = [arg.arg for arg in fn.args.args]
        num_params = len(param_names)
        num_defaults = len(fn.args.defaults)

        calls = [
            n for n in ast.walk(fn)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == fn.name
        ]

        if calls:
            # Recursive function
            call_arg_changes = []
            for call in calls:
                arg_changes = []
                for idx, arg_node in enumerate(call.args):
                    param_name = param_names[idx] if idx < len(param_names) else None
                    arg_changes.append(_classify_arg_change(arg_node, param_name))
                call_arg_changes.append(tuple(arg_changes))
            call_arg_changes_t = tuple(sorted(call_arg_changes))

            base_case_shape = _classify_base_case(fn, param_names)
            ret_shapes = _classify_recursive_return(fn, calls)

            fn_sigs.append(("recursive", num_params, call_arg_changes_t, base_case_shape, ret_shapes))
        else:
            # Non-recursive function
            ret_shapes = []
            for n in ast.walk(fn):
                if isinstance(n, ast.Return):
                    ret_shapes.append(_classify_non_rec_return_expr(n.value))
            fn_sigs.append(("non_recursive", num_params, num_defaults, tuple(sorted(ret_shapes))))

    return tuple(sorted(fn_sigs))


def _classify_arg_change(arg_node: ast.AST, param_name: Optional[str]) -> str:
    if isinstance(arg_node, ast.Name):
        if param_name and arg_node.id == param_name:
            return "unchanged"
        return "other"
    if isinstance(arg_node, ast.BinOp):
        is_p_left = isinstance(arg_node.left, ast.Name) and (arg_node.left.id == param_name or not param_name)
        is_p_right = isinstance(arg_node.right, ast.Name) and (arg_node.right.id == param_name or not param_name)
        is_c_left = isinstance(arg_node.left, ast.Constant)
        is_c_right = isinstance(arg_node.right, ast.Constant)

        if isinstance(arg_node.op, ast.Sub) and is_p_left and is_c_right:
            return "minus_constant"
        if isinstance(arg_node.op, ast.Add) and ((is_p_left and is_c_right) or (is_p_right and is_c_left)):
            return "plus_constant"
        if isinstance(arg_node.op, ast.FloorDiv) and is_p_left and is_c_right:
            return "integer_halving"
    if isinstance(arg_node, ast.Subscript):
        if isinstance(arg_node.value, ast.Name) and (arg_node.value.id == param_name or not param_name):
            if isinstance(arg_node.slice, ast.Slice):
                return "slicing"
    return "other"


def _classify_base_case(fn: ast.FunctionDef, param_names: List[str]) -> Tuple[str, ...]:
    shapes = []
    for node in ast.walk(fn):
        if isinstance(node, ast.If):
            test = node.test
            if isinstance(test, ast.Compare):
                left = test.left
                ops = test.ops
                comps = test.comparators
                if len(ops) == 1 and len(comps) == 1:
                    op = ops[0]
                    comp = comps[0]
                    if isinstance(left, ast.Call) and isinstance(left.func, ast.Name) and left.func.id == "len":
                        shapes.append("length_test")
                        continue
                    if isinstance(op, ast.Eq) and isinstance(comp, ast.Constant) and comp.value == 0:
                        shapes.append("eq_zero")
                        continue
                    if isinstance(op, (ast.Lt, ast.LtE)) and isinstance(comp, ast.Constant):
                        shapes.append("lt_or_lte_constant")
                        continue
                    if isinstance(op, (ast.Gt, ast.GtE)) and isinstance(comp, ast.Name) and comp.id in param_names:
                        shapes.append("gt_or_gte_param")
                        continue
                    if isinstance(op, (ast.Gt, ast.GtE)) and isinstance(comp, ast.Constant):
                        shapes.append("gt_or_gte_constant")
                        continue
            shapes.append("other_condition")
    return tuple(sorted(shapes))


def _classify_recursive_return(fn: ast.FunctionDef, calls: List[ast.Call]) -> Tuple[str, ...]:
    # Track any intermediate variable bound to a recursive call
    assigned_calls: Dict[str, ast.Call] = {}
    for stmt in fn.body:
        if isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                if (
                    isinstance(t, ast.Name)
                    and isinstance(stmt.value, ast.Call)
                    and isinstance(stmt.value.func, ast.Name)
                    and stmt.value.func.id == fn.name
                ):
                    assigned_calls[t.id] = stmt.value

    shapes = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Return) and node.value is not None:
            expr = node.value
            # Pass-through self call: return fn(...)
            if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and expr.func.id == fn.name:
                shapes.append("pass_through")
                continue

            expr_calls = [
                n for n in ast.walk(expr)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == fn.name
            ]
            expr_assigned = [
                n.id for n in ast.walk(expr)
                if isinstance(n, ast.Name) and n.id in assigned_calls
            ]

            if not expr_calls and not expr_assigned:
                continue

            has_mult = any(isinstance(n.op, ast.Mult) for n in ast.walk(expr) if isinstance(n, ast.BinOp))
            if has_mult:
                shapes.append("numeric_mult")
                continue

            has_add = any(isinstance(n.op, ast.Add) for n in ast.walk(expr) if isinstance(n, ast.BinOp))
            if has_add:
                str_constants = [
                    n.value for n in ast.walk(expr)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)
                ]
                has_str_call = any(
                    isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "str"
                    for n in ast.walk(expr)
                )
                has_subscript = any(isinstance(n, ast.Subscript) for n in ast.walk(expr))

                if str_constants or has_str_call or has_subscript:
                    shapes.append("string_concat")
                else:
                    shapes.append("numeric_add")
                continue

            shapes.append("other_recursive_return")

    return tuple(sorted(shapes))


def _classify_non_rec_return_expr(node: Optional[ast.AST]) -> str:
    if node is None:
        return "None"
    if isinstance(node, ast.BinOp):
        return f"BinOp_{type(node.op).__name__}"
    if isinstance(node, ast.Constant):
        return f"Constant_{type(node.value).__name__}"
    if isinstance(node, ast.Name):
        return "Name"
    if isinstance(node, ast.Call):
        return "Call"
    return type(node).__name__


def find_heldout_similarity_flags(pack_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Compare every held-out item against every learner-visible source in the pack.

    Returns a list of flags:
      {
        'held_out_id': item_id,
        'held_out_family': family_id,
        'signature': signature,
        'matched_sources': [{'id': ..., 'family_id': ..., 'source_type': ...}, ...]
      }
    """
    held_out_items, learner_sources = extract_code_snippets_from_pack(pack_data)

    source_sig_map: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
    for source in learner_sources:
        sig = compute_code_signature(source["body"])
        source_sig_map.setdefault(sig, []).append(source)

    flags = []
    for item in held_out_items:
        sig = compute_code_signature(item["body"])
        matched = source_sig_map.get(sig)
        if matched:
            flags.append({
                "held_out_id": item["id"],
                "held_out_family": item["family_id"],
                "signature": sig,
                "matched_sources": matched,
            })

    return flags

import json
from pathlib import Path
import re
import unittest

from aesop_lab.content import ContentValidationError, load_pack, parse_pack, validate_pack
from aesop_lab.domain.models import ActivityType, EvidenceKind, HintLevel

PACK_PATH = Path(__file__).resolve().parents[1] / "content" / "packs" / "python-functions-recursion" / "pack.json"


def raw_pack() -> dict:
    return json.loads(PACK_PATH.read_text(encoding="utf-8"))


def codes(raw: dict) -> set[str]:
    return {issue.code for issue in validate_pack(raw)}


def raw_item(raw: dict, item_id: str) -> dict:
    return next(item for item in raw["items"] if item["id"] == item_id)


def code_lines(text: str) -> set[str]:
    """Unindented code lines (defs, assignments, calls) with comments and spacing normalised."""
    lines = set()
    for line in text.splitlines():
        if line and not line[0].isspace():
            lines.add(re.sub(r"\s+", " ", line.split("#")[0]).strip())
    lines.discard("")
    return lines


def lesson_code_blocks(raw: dict) -> list[str]:
    fence = re.compile(r"```python\n(.*?)```", re.S)
    return [block for lesson in raw["lessons"] for block in fence.findall(lesson["body"])]


def reviewed_raw() -> dict:
    """A pack with approvals for every record, as a reviewer other than the author would record them."""
    raw = raw_pack()
    raw["status"] = "reviewed"
    for item in raw["items"]:
        if item.get("answer_key"):
            item["answer_key"]["status"] = "reviewed"
    scope = ([concept["id"] for concept in raw["concepts"]] + [lesson["id"] for lesson in raw["lessons"]]
             + [item["id"] for item in raw["items"]] + [source["id"] for source in raw["sources"]]
             + [item["rubric"]["id"] for item in raw["items"] if item.get("rubric")])
    raw["review"]["receipts"] = [{"reviewer": "Independent reviewer", "reviewed_on": "2026-10-14",
                                  "outcome": "approved", "scope_ids": scope}]
    return raw


class ShippedPackTests(unittest.TestCase):
    def test_shipped_pack_validates_without_issues(self) -> None:
        self.assertEqual(validate_pack(raw_pack()), ())
        self.assertEqual(load_pack(PACK_PATH).pack_id, "python-functions-recursion")

    def test_pack_is_an_honest_draft(self) -> None:
        pack = load_pack(PACK_PATH)
        self.assertEqual(pack.status, "draft")
        self.assertEqual(pack.receipts, ())
        self.assertTrue(all(item.answer_key.status == "candidate"
                            for item in pack.items if item.answer_key is not None))

    def test_five_concepts_form_a_prerequisite_graph(self) -> None:
        pack = load_pack(PACK_PATH)
        self.assertEqual(len(pack.concepts), 5)
        order = pack.learning_order()
        self.assertEqual(order.index("function-definition-and-return"), 0)
        self.assertEqual(
            pack.prerequisites_of("recursive-case-and-trace"),
            frozenset({"base-case", "recursion-as-self-call",
                       "parameters-and-local-scope", "function-definition-and-return"}),
        )
        for concept in pack.concepts:
            for prerequisite in concept.prerequisite_ids:
                self.assertLess(order.index(prerequisite), order.index(concept.id))

    def test_every_concept_has_lessons_families_and_a_held_out_check(self) -> None:
        pack = load_pack(PACK_PATH)
        for concept in pack.concepts:
            with self.subTest(concept=concept.id):
                items = pack.items_for(concept.id)
                self.assertTrue(any(lesson.concept_id == concept.id for lesson in pack.lessons))
                self.assertGreaterEqual(len({item.activity.family_id for item in items}), 2)
                self.assertTrue(any(item.activity.held_out and item.activity.evidence_kind in (
                    EvidenceKind.APPLICATION, EvidenceKind.TRANSFER) for item in items))
                self.assertTrue(any(item.activity.activity_type in (
                    ActivityType.CHOICE, ActivityType.TRACE) for item in items))

    def test_candidate_keys_match_the_snippets_they_grade(self) -> None:
        # Trusted authored content, run only by this test to confirm each candidate key.
        pack = load_pack(PACK_PATH)
        checked = 0
        for item in pack.items:
            if item.check_expression is None:
                continue
            with self.subTest(item=item.id):
                namespace: dict = {}
                exec(item.body, namespace)
                value = str(eval(item.check_expression, namespace))
                self.assertIn(value, item.answer_key.accepted)
                checked += 1
        self.assertGreaterEqual(checked, 8)

    def test_every_trace_item_has_a_check_expression(self) -> None:
        for item in load_pack(PACK_PATH).items:
            if item.activity.activity_type is ActivityType.TRACE:
                self.assertIsNotNone(item.check_expression, item.id)

    def test_hint_ladders_are_complete_and_ordered(self) -> None:
        for item in load_pack(PACK_PATH).items:
            with self.subTest(item=item.id):
                self.assertEqual(tuple(hint.level for hint in item.hints),
                                 (HintLevel.NUDGE, HintLevel.TARGETED, HintLevel.WORKED_SOLUTION))

    def test_ungraded_items_have_rubrics_and_no_keys(self) -> None:
        ungraded = [item for item in load_pack(PACK_PATH).items
                    if item.activity.activity_type in (ActivityType.EXPLANATION, ActivityType.CODE_DESIGN)]
        self.assertGreaterEqual(len(ungraded), 3)
        for item in ungraded:
            with self.subTest(item=item.id):
                self.assertIsNotNone(item.rubric)
                self.assertIsNone(item.answer_key)

    def test_every_source_is_official_python_docs_and_is_cited(self) -> None:
        pack = load_pack(PACK_PATH)
        cited = {source_id for lesson in pack.lessons for source_id in lesson.source_ids}
        cited |= {source_id for item in pack.items for source_id in item.source_ids}
        for source in pack.sources:
            with self.subTest(source=source.id):
                self.assertTrue(source.url.startswith("https://docs.python.org/3.12/"))
                self.assertIn(source.id, cited)

    def test_items_do_not_repeat_lesson_examples_or_inputs(self) -> None:
        raw = raw_pack()
        taught_lines = set().union(*(code_lines(block) for block in lesson_code_blocks(raw)))
        taught_blocks = {re.sub(r"\s+", " ", block).strip() for block in lesson_code_blocks(raw)}
        for item in raw["items"]:
            with self.subTest(item=item["id"]):
                self.assertEqual(code_lines(item["body"]) & taught_lines, set())
                body = re.sub(r"\s+", " ", item["body"])
                self.assertFalse(any(block in body for block in taught_blocks))

    def test_held_out_items_do_not_repeat_other_items(self) -> None:
        raw = raw_pack()
        for held_out in (item for item in raw["items"] if item["held_out"]):
            others = set().union(*(code_lines(item["body"]) for item in raw["items"] if item is not held_out))
            with self.subTest(item=held_out["id"]):
                self.assertEqual(code_lines(held_out["body"]) & others, set())

    def test_halving_transfer_item_differs_from_the_lesson_example(self) -> None:
        body = raw_item(raw_pack(), "recursion-halving-transfer-01")["body"]
        self.assertNotIn("steps(8)", body)
        self.assertNotIn("def steps", body)


class ValidatorRejectsBrokenPacksTests(unittest.TestCase):
    def test_missing_field_is_reported_by_path(self) -> None:
        raw = raw_pack()
        del raw["concepts"][0]["title"]
        issues = validate_pack(raw)
        self.assertIn(("concepts[0].title", "missing_field"),
                      {(issue.path, issue.code) for issue in issues})

    def test_all_problems_are_collected_in_one_pass(self) -> None:
        raw = raw_pack()
        raw["sources"][0]["url"] = "https://example.com/python"
        raw_item(raw, "def-return-choice-01")["answer_key"]["accepted"] = ["return total * 2"]
        issue_codes = codes(raw)
        self.assertIn("invalid_url", issue_codes)
        self.assertIn("choice_key_invalid", issue_codes)

    def test_prerequisite_cycle_is_rejected(self) -> None:
        raw = raw_pack()
        raw["concepts"][0]["prerequisite_ids"] = ["recursive-case-and-trace"]
        self.assertIn("cycle", codes(raw))

    def test_unknown_prerequisite_is_rejected(self) -> None:
        raw = raw_pack()
        raw["concepts"][2]["prerequisite_ids"].append("loops")
        self.assertIn("unknown_reference", codes(raw))

    def test_sources_must_be_official_python_docs(self) -> None:
        raw = raw_pack()
        raw["sources"].append({"id": "blog", "title": "A blog", "url": "https://blog.example.org/recursion"})
        self.assertIn("invalid_url", codes(raw))

    def test_choice_key_must_be_a_listed_choice(self) -> None:
        raw = raw_pack()
        raw_item(raw, "scope-global-choice-01")["answer_key"]["accepted"] = ["11"]
        self.assertIn("choice_key_invalid", codes(raw))

    def test_trace_items_need_a_check_expression(self) -> None:
        raw = raw_pack()
        del raw_item(raw, "base-case-trace-01")["check_expression"]
        self.assertIn("check_missing", codes(raw))

    def test_scored_items_need_a_key(self) -> None:
        raw = raw_pack()
        del raw_item(raw, "recursion-recognize-choice-01")["answer_key"]
        self.assertIn("answer_key_missing", codes(raw))

    def test_explanations_cannot_carry_a_key(self) -> None:
        raw = raw_pack()
        raw_item(raw, "recursion-explain-01")["answer_key"] = {"status": "candidate", "accepted": ["yes"]}
        self.assertIn("ungraded_key", codes(raw))

    def test_ungraded_items_need_a_rubric(self) -> None:
        raw = raw_pack()
        del raw_item(raw, "base-case-explain-01")["rubric"]
        self.assertIn("rubric_missing", codes(raw))

    def test_transfer_evidence_must_be_held_out(self) -> None:
        raw = raw_pack()
        raw_item(raw, "recursive-case-transfer-01")["held_out"] = False
        self.assertIn("domain_invalid", codes(raw))

    def test_hint_ladder_must_be_complete_and_in_order(self) -> None:
        raw = raw_pack()
        raw_item(raw, "base-case-trace-01")["hints"].reverse()
        self.assertIn("hint_ladder", codes(raw))
        raw = raw_pack()
        del raw_item(raw, "base-case-trace-01")["hints"][1]
        self.assertIn("hint_ladder", codes(raw))

    def test_worked_solution_cannot_be_the_only_hint(self) -> None:
        raw = raw_pack()
        raw_item(raw, "base-case-trace-01")["hints"] = [
            {"level": "worked_solution", "text": "f(2) is 2."}]
        self.assertIn("hint_ladder", codes(raw))

    def test_concept_without_a_held_out_check_is_rejected(self) -> None:
        raw = raw_pack()
        raw_item(raw, "base-case-transfer-01")["held_out"] = False
        raw_item(raw, "base-case-transfer-01")["evidence_kind"] = "recall"
        self.assertIn("coverage", codes(raw))

    def test_concept_needs_two_item_families(self) -> None:
        raw = raw_pack()
        for item in raw["items"]:
            if item["concept_id"] == "base-case":
                item["family_id"] = "base-case-only-family"
        self.assertIn("coverage", codes(raw))

    def test_lesson_and_item_must_match_concept_version(self) -> None:
        raw = raw_pack()
        raw["lessons"][0]["content_version"] = "v2"
        raw_item(raw, "base-case-choice-01")["content_version"] = "v9"
        self.assertIn("content_version_mismatch", codes(raw))

    def test_unknown_source_reference_is_rejected(self) -> None:
        raw = raw_pack()
        raw_item(raw, "base-case-choice-01")["source_ids"] = ["py-missing"]
        self.assertIn("unknown_reference", codes(raw))

    def test_duplicate_ids_are_rejected(self) -> None:
        raw = raw_pack()
        raw["items"][1]["id"] = raw["items"][0]["id"]
        self.assertIn("duplicate_id", codes(raw))

    def test_unknown_enum_values_are_rejected(self) -> None:
        raw = raw_pack()
        raw_item(raw, "base-case-choice-01")["evidence_kind"] = "mastery"
        raw_item(raw, "base-case-choice-01")["activity_type"] = "essay"
        self.assertIn("unknown_value", codes(raw))

    def test_draft_pack_cannot_claim_reviewed_keys(self) -> None:
        raw = raw_pack()
        raw_item(raw, "base-case-trace-01")["answer_key"]["status"] = "reviewed"
        self.assertIn("review_claimed", codes(raw))

    def test_reviewed_pack_needs_receipts_for_every_record(self) -> None:
        raw = raw_pack()
        raw["status"] = "reviewed"
        for item in raw["items"]:
            if item.get("answer_key"):
                item["answer_key"]["status"] = "reviewed"
        self.assertIn("review_claimed", codes(raw))

    def test_complete_receipts_let_a_reviewed_pack_validate(self) -> None:
        self.assertEqual(validate_pack(reviewed_raw()), ())

    def test_reviewed_pack_needs_an_approved_receipt_for_every_source(self) -> None:
        raw = reviewed_raw()
        missing = raw["sources"][0]["id"]
        raw["review"]["receipts"][0]["scope_ids"].remove(missing)
        self.assertIn((missing, "review_claimed"), {(issue.path, issue.code) for issue in validate_pack(raw)})

    def test_reviewed_pack_needs_an_approved_receipt_for_every_rubric(self) -> None:
        raw = reviewed_raw()
        missing = raw_item(raw, "recursion-explain-01")["rubric"]["id"]
        raw["review"]["receipts"][0]["scope_ids"].remove(missing)
        self.assertIn((missing, "review_claimed"), {(issue.path, issue.code) for issue in validate_pack(raw)})

    def test_non_approved_receipt_does_not_cover_sources_or_rubrics(self) -> None:
        raw = reviewed_raw()
        raw["review"]["receipts"][0]["outcome"] = "changes_requested"
        flagged = {issue.path for issue in validate_pack(raw) if issue.code == "review_claimed"}
        self.assertIn(raw["sources"][0]["id"], flagged)
        self.assertIn("base-case-explain-rubric", flagged)

    def test_receipt_may_scope_sources_and_rubrics(self) -> None:
        raw = raw_pack()
        raw["review"]["receipts"] = [{
            "reviewer": "Independent reviewer", "reviewed_on": "2026-10-13", "outcome": "changes_requested",
            "scope_ids": ["py-ref-calls", "recursion-explain-rubric"],
        }]
        self.assertEqual(validate_pack(raw), ())

    def test_rubric_ids_must_not_collide_with_other_records(self) -> None:
        raw = raw_pack()
        raw_item(raw, "base-case-explain-01")["rubric"]["id"] = "recursion-explain-rubric"
        self.assertIn("duplicate_id", codes(raw))
        raw = raw_pack()
        raw_item(raw, "base-case-explain-01")["rubric"]["id"] = "py-ref-calls"
        self.assertIn("duplicate_id", codes(raw))

    def test_reviewer_cannot_be_the_author(self) -> None:
        raw = raw_pack()
        raw["review"]["receipts"] = [{
            "reviewer": raw["author"], "reviewed_on": "2026-10-12",
            "outcome": "approved", "scope_ids": ["base-case"],
        }]
        self.assertIn("review_invalid", codes(raw))

    def test_receipt_scope_must_name_real_records(self) -> None:
        raw = raw_pack()
        raw["review"]["receipts"] = [{
            "reviewer": "Independent reviewer", "reviewed_on": "2026-10-13",
            "outcome": "approved", "scope_ids": ["no-such-record"],
        }]
        self.assertIn("unknown_reference", codes(raw))

    def test_parse_pack_raises_with_every_issue(self) -> None:
        raw = raw_pack()
        raw["sources"][0]["url"] = "https://example.com/a"
        raw["concepts"][0]["prerequisite_ids"] = ["recursive-case-and-trace"]
        with self.assertRaises(ContentValidationError) as ctx:
            parse_pack(raw)
        self.assertGreaterEqual(len(ctx.exception.issues), 2)

    def test_parsed_records_use_domain_types(self) -> None:
        item = next(item for item in load_pack(PACK_PATH).items if item.id == "recursive-case-transfer-01")
        self.assertIs(item.activity.evidence_kind, EvidenceKind.TRANSFER)
        self.assertTrue(item.activity.held_out)
        self.assertIs(item.hints[0].level, HintLevel.NUDGE)


if __name__ == "__main__":
    unittest.main()

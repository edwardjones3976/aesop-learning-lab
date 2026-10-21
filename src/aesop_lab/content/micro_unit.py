"""Strict standalone micro-unit packs. No scheduling or scoring side effects."""
from __future__ import annotations
import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping
from .errors import ContentValidationError, Issue
from .model import AnswerKeyCandidate

MICRO_UNIT_SCHEMA_VERSION = "micro-unit-pack/1"

@dataclass(frozen=True, slots=True)
class TeachingMethod:
    id: str
    name: str
    description: str

@dataclass(frozen=True, slots=True)
class Target:
    word: str
    gloss: str

@dataclass(frozen=True, slots=True)
class PracticeItem:
    id: str
    prompt: str

@dataclass(frozen=True, slots=True)
class DelayedCheck:
    id: str
    family_id: str
    prompt: str
    answer_key: AnswerKeyCandidate
    check_delay_days: int
    held_out: bool

@dataclass(frozen=True, slots=True)
class MicroUnit:
    id: str
    target: Target
    variants: Mapping[str, str]
    check: DelayedCheck
    practice: tuple[PracticeItem, ...]

@dataclass(frozen=True, slots=True)
class MicroUnitPack:
    kind: str
    schema_version: str
    pack_id: str
    methods: tuple[TeachingMethod, ...]
    units: tuple[MicroUnit, ...]

class _Reader:
    def __init__(self):
        self.issues = []
        self.seen = {}

    def issue(self, path, code, message):
        self.issues.append(Issue(path, code, message))

    def obj(self, value, path, fields, optional=()):
        if not isinstance(value, dict):
            self.issue(path, "wrong_type", "expected an object")
            return {}
        for key in fields:
            if key not in value:
                self.issue(f"{path}.{key}".lstrip("."), "missing_field", f"{key} is required")
        for key in value.keys() - set(fields) - set(optional):
            self.issue(f"{path}.{key}".lstrip("."), "unknown_field", "field is not in this schema")
        return value

    def text(self, value, path):
        if not isinstance(value, str) or not value.strip():
            self.issue(path, "wrong_type", "expected a non-empty string")
            return ""
        return value

    def array(self, value, path, nonempty=False):
        if not isinstance(value, list):
            self.issue(path, "wrong_type", "expected an array")
            return []
        if nonempty and not value:
            self.issue(path, "empty_list", "must contain at least one entry")
        return value

    def identifier(self, value, path, namespace):
        value = self.text(value, path)
        ids = self.seen.setdefault(namespace, set())
        if value in ids:
            self.issue(path, "duplicate_id", f"duplicate {namespace} ID: {value}")
        ids.add(value)
        return value

    def unit(self, value, p, method_ids):
        u = self.obj(value, p, ("id", "target", "variants", "check"), ("practice",))
        uid = self.identifier(u.get("id"), p + ".id", "unit")
        t = self.obj(u.get("target"), p + ".target", ("word", "gloss"))
        target = Target(self.text(t.get("word"), p + ".target.word"), self.text(t.get("gloss"), p + ".target.gloss"))
        variants = u.get("variants")
        if not isinstance(variants, dict):
            self.issue(p + ".variants", "wrong_type", "expected method IDs mapped to lesson strings")
            variants = {}
        for mid in method_ids - variants.keys():
            self.issue(p + ".variants." + mid, "missing_variant", "declared method needs exactly one lesson")
        for mid in variants.keys() - method_ids:
            self.issue(p + ".variants." + str(mid), "unknown_method", "method is not declared by the pack")
        lessons = {mid: self.text(body, p + ".variants." + str(mid)) for mid, body in variants.items()}
        cp = p + ".check"
        c = self.obj(u.get("check"), cp, ("id", "family_id", "prompt", "answer_key", "check_delay_days", "held_out"))
        cid = self.identifier(c.get("id"), cp + ".id", "item")
        family = self.identifier(c.get("family_id"), cp + ".family_id", "family")
        prompt = self.text(c.get("prompt"), cp + ".prompt")
        k = self.obj(c.get("answer_key"), cp + ".answer_key", ("status", "accepted"))
        if k.get("status") != "candidate":
            self.issue(cp + ".answer_key.status", "candidate_key_required", "check key must have status candidate")
        accepted = tuple(self.text(a, f"{cp}.answer_key.accepted[{j}]") for j, a in enumerate(self.array(k.get("accepted"), cp + ".answer_key.accepted", True)))
        if len(set(accepted)) != len(accepted):
            self.issue(cp + ".answer_key.accepted", "duplicate_answer", "accepted answers must be unique")
        if type(c.get("check_delay_days")) is not int or c["check_delay_days"] != 7:
            self.issue(cp + ".check_delay_days", "invalid_delay", "expected integer 7")
        if c.get("held_out") is not True:
            self.issue(cp + ".held_out", "held_out_required", "check must be held out")
        # Lessons exist to teach the answer, so only the check prompt is guarded. Whole
        # words, ignoring case, so "me" does not match "mean".
        for answer in accepted:
            if answer and re.search(rf"(?<!\w){re.escape(answer)}(?!\w)", prompt, re.IGNORECASE):
                self.issue(cp + ".prompt", "answer_leak", "prompt contains its accepted answer")
        practice = []
        for j, value in enumerate(self.array(u.get("practice", []), p + ".practice")):
            pp = f"{p}.practice[{j}]"
            item = self.obj(value, pp, ("id", "prompt"))
            practice.append(PracticeItem(self.identifier(item.get("id"), pp + ".id", "item"), self.text(item.get("prompt"), pp + ".prompt")))
        return MicroUnit(uid, target, MappingProxyType(lessons), DelayedCheck(cid, family, prompt, AnswerKeyCandidate(accepted, "candidate"), 7, True), tuple(practice))

    def parse(self, data):
        raw = self.obj(data, "", ("kind", "schema_version", "pack_id", "methods", "units"))
        for key, expected in (("kind", "micro_unit"), ("schema_version", MICRO_UNIT_SCHEMA_VERSION)):
            if raw.get(key) != expected:
                self.issue(key, "unknown_value", f"expected {expected!r}")
        pack_id = self.text(raw.get("pack_id"), "pack_id")
        methods = []
        for i, value in enumerate(self.array(raw.get("methods"), "methods", True)):
            p = f"methods[{i}]"
            m = self.obj(value, p, ("id", "name", "description"))
            methods.append(TeachingMethod(self.identifier(m.get("id"), p + ".id", "method"), self.text(m.get("name"), p + ".name"), self.text(m.get("description"), p + ".description")))
        units = tuple(self.unit(value, f"units[{i}]", {m.id for m in methods}) for i, value in enumerate(self.array(raw.get("units"), "units", True)))
        return MicroUnitPack("micro_unit", MICRO_UNIT_SCHEMA_VERSION, pack_id, tuple(methods), units)


def validate_micro_unit_pack(data: object) -> tuple[Issue, ...]:
    reader = _Reader()
    reader.parse(data)
    return tuple(reader.issues)


def parse_micro_unit_pack(data: object) -> MicroUnitPack:
    reader = _Reader()
    pack = reader.parse(data)
    if reader.issues:
        raise ContentValidationError(tuple(reader.issues))
    return pack


def load_micro_unit_pack(path: str | Path) -> MicroUnitPack:
    return parse_micro_unit_pack(json.loads(Path(path).read_text(encoding="utf-8")))

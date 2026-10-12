"""Parse and validate content packs. Every problem is collected, then reported together."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

from aesop_lab.domain.models import Activity, ActivityType, Concept, EvidenceKind, HintLevel

from .errors import ContentValidationError, Issue
from .model import (
    CONTENT_SCHEMA_VERSION,
    HELD_OUT_EVIDENCE,
    KEY_STATUSES,
    MIN_FAMILIES_PER_CONCEPT,
    PACK_STATUSES,
    PYTHON_DOCS_PREFIX,
    RECEIPT_OUTCOMES,
    REQUIRED_HINT_LEVELS,
    SCORED_TYPES,
    UNGRADED_TYPES,
    AnswerKeyCandidate,
    ContentPack,
    CriterionSpec,
    HintSpec,
    ItemContent,
    Lesson,
    ReviewReceipt,
    RubricSpec,
    Source,
    topological_order,
)


def validate_pack(data: Any) -> tuple[Issue, ...]:
    """Return every problem in a raw pack. An empty tuple means the pack is valid."""
    _, issues = _parse(data)
    return tuple(issues)


def parse_pack(data: Any) -> ContentPack:
    pack, issues = _parse(data)
    if issues or pack is None:
        raise ContentValidationError(tuple(issues))
    return pack


def load_pack(path: str | Path) -> ContentPack:
    return parse_pack(json.loads(Path(path).read_text(encoding="utf-8")))


def _parse(data: Any) -> tuple[ContentPack | None, list[Issue]]:
    issues: list[Issue] = []
    if not isinstance(data, Mapping):
        return None, [Issue("", "wrong_type", "the pack must be a JSON object")]

    schema = _field(data, "schema_version", str, "", issues)
    if schema is not None and schema != CONTENT_SCHEMA_VERSION:
        issues.append(Issue("schema_version", "schema_version", f"expected {CONTENT_SCHEMA_VERSION}"))
    pack_id = _field(data, "pack_id", str, "", issues)
    pack_version = _field(data, "pack_version", str, "", issues)
    topic = _field(data, "topic", str, "", issues)
    status = _enum_text(data, "status", PACK_STATUSES, "", issues)
    author = _field(data, "author", str, "", issues)

    seen: dict[str, str] = {}
    sources = _parse_sources(data, seen, issues)
    concepts = _parse_concepts(data, seen, issues)
    lessons = _parse_lessons(data, seen, concepts, sources, issues)
    items = _parse_items(data, seen, concepts, sources, issues)
    receipts = _parse_receipts(data, issues)

    if concepts is not None and lessons is not None and items is not None:
        _check_coverage(concepts, lessons, items, issues)
    if None not in (status, author) and concepts is not None and lessons is not None and items is not None:
        _check_review(status, author, concepts, lessons, items, receipts, issues)

    if issues or None in (pack_id, pack_version, topic, status, author) or concepts is None:
        return None, issues
    pack = ContentPack(
        schema_version=CONTENT_SCHEMA_VERSION,
        pack_id=pack_id,
        pack_version=pack_version,
        topic=topic,
        status=status,
        author=author,
        concepts=tuple(concepts),
        lessons=tuple(lessons or ()),
        items=tuple(items or ()),
        sources=tuple(sources or ()),
        receipts=tuple(receipts or ()),
    )
    return pack, issues


# ---------------------------------------------------------------- primitives

def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _field(raw: Mapping[str, Any], key: str, kind: type, path: str, issues: list[Issue],
           *, required: bool = True, default: Any = None, allow_empty: bool = False) -> Any:
    """Read one field. Returns None (and records an issue) when it is missing or the wrong type."""
    where = _join(path, key)
    if key not in raw:
        if required:
            issues.append(Issue(where, "missing_field", f"'{key}' is required"))
            return None
        return default
    value = raw[key]
    if kind is str:
        if not isinstance(value, str) or (not allow_empty and not value.strip()):
            issues.append(Issue(where, "wrong_type", f"'{key}' must be a non-empty string"))
            return None
    elif not isinstance(value, kind):
        issues.append(Issue(where, "wrong_type", f"'{key}' must be a {kind.__name__}"))
        return None
    return value


def _enum_text(raw: Mapping[str, Any], key: str, allowed: tuple[str, ...], path: str,
               issues: list[Issue]) -> str | None:
    value = _field(raw, key, str, path, issues)
    if value is None:
        return None
    if value not in allowed:
        issues.append(Issue(_join(path, key), "unknown_value", f"'{key}' must be one of {', '.join(allowed)}"))
        return None
    return value


def _str_list(raw: Mapping[str, Any], key: str, path: str, issues: list[Issue],
              *, required: bool = True) -> tuple[str, ...] | None:
    values = _field(raw, key, list, path, issues, required=required, default=[])
    if values is None:
        return None
    cleaned: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            issues.append(Issue(f"{_join(path, key)}[{index}]", "wrong_type", "entries must be non-empty strings"))
            return None
        cleaned.append(value)
    return tuple(cleaned)


def _entries(container: Mapping[str, Any], key: str, issues: list[Issue]) -> list[tuple[str, Mapping[str, Any]]]:
    values = _field(container, key, list, "", issues, required=False, default=[])
    entries: list[tuple[str, Mapping[str, Any]]] = []
    for index, raw in enumerate(values):
        path = f"{key}[{index}]"
        if isinstance(raw, Mapping):
            entries.append((path, raw))
        else:
            issues.append(Issue(path, "wrong_type", "each entry must be an object"))
    return entries


def _register(record_id: str | None, path: str, seen: dict[str, str], issues: list[Issue]) -> bool:
    if record_id is None:
        return False
    if record_id in seen:
        issues.append(Issue(path, "duplicate_id", f"'{record_id}' is already used at {seen[record_id]}"))
        return False
    seen[record_id] = path
    return True


def _normalize(text: str) -> str:
    # Same rule as aesop_lab.assessment.normalize_answer: collapse whitespace, keep case and punctuation.
    return " ".join(text.split())


# ---------------------------------------------------------------- records

def _parse_sources(data: Mapping[str, Any], seen: dict[str, str], issues: list[Issue]) -> list[Source] | None:
    sources: list[Source] = []
    for path, raw in _entries(data, "sources", issues):
        source_id = _field(raw, "id", str, path, issues)
        title = _field(raw, "title", str, path, issues)
        url = _field(raw, "url", str, path, issues)
        if url is not None and not url.startswith(PYTHON_DOCS_PREFIX):
            # Keep the source registered so citations of it are not reported as a second, unrelated defect.
            issues.append(Issue(_join(path, "url"), "invalid_url",
                                f"sources must be official Python documentation under {PYTHON_DOCS_PREFIX}"))
        if None in (source_id, title, url):
            continue
        if _register(source_id, path, seen, issues):
            sources.append(Source(source_id, title, url))
    return sources


def _parse_concepts(data: Mapping[str, Any], seen: dict[str, str], issues: list[Issue]) -> list[Concept] | None:
    raw_concepts = _entries(data, "concepts", issues)
    concepts: list[Concept] = []
    for path, raw in raw_concepts:
        concept_id = _field(raw, "id", str, path, issues)
        title = _field(raw, "title", str, path, issues)
        content_version = _field(raw, "content_version", str, path, issues)
        prerequisites = _str_list(raw, "prerequisite_ids", path, issues, required=False)
        if None in (concept_id, title, content_version, prerequisites):
            continue
        if not _register(concept_id, path, seen, issues):
            continue
        try:
            concepts.append(Concept(concept_id, title, content_version, prerequisites))
        except ValueError as exc:
            issues.append(Issue(path, "domain_invalid", str(exc)))

    known = {concept.id for concept in concepts}
    unknown_refs = False
    for concept in concepts:
        for prerequisite in concept.prerequisite_ids:
            if prerequisite not in known:
                unknown_refs = True
                issues.append(Issue(f"concepts[{concept.id}].prerequisite_ids", "unknown_reference",
                                    f"'{prerequisite}' is not a concept in this pack"))
    if not unknown_refs and concepts:
        try:
            topological_order({concept.id: concept.prerequisite_ids for concept in concepts})
        except ValueError as exc:
            issues.append(Issue("concepts", "cycle", str(exc)))
    return concepts


def _parse_lessons(data: Mapping[str, Any], seen: dict[str, str], concepts: list[Concept] | None,
                   sources: list[Source] | None, issues: list[Issue]) -> list[Lesson] | None:
    if concepts is None or sources is None:
        return None
    concept_versions = {concept.id: concept.content_version for concept in concepts}
    source_ids = {source.id for source in sources}
    lessons: list[Lesson] = []
    for path, raw in _entries(data, "lessons", issues):
        lesson_id = _field(raw, "id", str, path, issues)
        concept_id = _field(raw, "concept_id", str, path, issues)
        content_version = _field(raw, "content_version", str, path, issues)
        title = _field(raw, "title", str, path, issues)
        body = _field(raw, "body", str, path, issues)
        cited = _str_list(raw, "source_ids", path, issues)
        if None in (lesson_id, concept_id, content_version, title, body, cited):
            continue
        if not _register(lesson_id, path, seen, issues):
            continue
        if concept_id not in concept_versions:
            issues.append(Issue(_join(path, "concept_id"), "unknown_reference", f"'{concept_id}' is not a concept"))
            continue
        if content_version != concept_versions[concept_id]:
            issues.append(Issue(_join(path, "content_version"), "content_version_mismatch",
                                "a lesson must share its concept's content version"))
        _check_sources(cited, path, source_ids, issues)
        lessons.append(Lesson(lesson_id, concept_id, content_version, title, body, cited))
    return lessons


def _parse_items(data: Mapping[str, Any], seen: dict[str, str], concepts: list[Concept] | None,
                 sources: list[Source] | None, issues: list[Issue]) -> list[ItemContent] | None:
    if concepts is None or sources is None:
        return None
    concept_versions = {concept.id: concept.content_version for concept in concepts}
    source_ids = {source.id for source in sources}
    items: list[ItemContent] = []
    for path, raw in _entries(data, "items", issues):
        item = _parse_item(raw, path, seen, concept_versions, source_ids, issues)
        if item is not None:
            items.append(item)
    return items


def _parse_item(raw: Mapping[str, Any], path: str, seen: dict[str, str],
                concept_versions: Mapping[str, str], source_ids: set[str],
                issues: list[Issue]) -> ItemContent | None:
    item_id = _field(raw, "id", str, path, issues)
    concept_id = _field(raw, "concept_id", str, path, issues)
    content_version = _field(raw, "content_version", str, path, issues)
    family_id = _field(raw, "family_id", str, path, issues)
    activity_type = _enum_value(raw, "activity_type", ActivityType, path, issues)
    evidence_kind = _enum_value(raw, "evidence_kind", EvidenceKind, path, issues)
    held_out = _field(raw, "held_out", bool, path, issues, required=False, default=False)
    prompt = _field(raw, "prompt", str, path, issues)
    body = _field(raw, "body", str, path, issues, required=False, default="", allow_empty=True)
    choices = _str_list(raw, "choices", path, issues, required=False)
    cited = _str_list(raw, "source_ids", path, issues)
    check_expression = _field(raw, "check_expression", str, path, issues, required=False, default=None)
    key = _parse_key(raw, path, issues)
    rubric = _parse_rubric(raw, path, issues)
    hints = _parse_hints(raw, path, issues)

    if None in (item_id, concept_id, content_version, family_id, activity_type, evidence_kind,
                held_out, prompt, body, choices, cited, hints):
        return None
    if not _register(item_id, path, seen, issues):
        return None
    if concept_id not in concept_versions:
        issues.append(Issue(_join(path, "concept_id"), "unknown_reference", f"'{concept_id}' is not a concept"))
        return None
    if content_version != concept_versions[concept_id]:
        issues.append(Issue(_join(path, "content_version"), "content_version_mismatch",
                            "an item must share its concept's content version"))
    _check_sources(cited, path, source_ids, issues)

    try:
        activity = Activity(item_id, concept_id, content_version, family_id,
                            activity_type, evidence_kind, held_out)
    except ValueError as exc:
        issues.append(Issue(path, "domain_invalid", str(exc)))
        return None

    before = len(issues)
    _check_item_shape(activity_type, path, choices, key, check_expression, rubric, hints, issues)
    if len(issues) > before:
        return None
    return ItemContent(activity, prompt, body, choices, key, check_expression, rubric, hints, cited)


def _enum_value(raw: Mapping[str, Any], key: str, enum_type: type, path: str, issues: list[Issue]) -> Any:
    value = _field(raw, key, str, path, issues)
    if value is None:
        return None
    try:
        return enum_type(value)
    except ValueError:
        allowed = ", ".join(member.value for member in enum_type)
        issues.append(Issue(_join(path, key), "unknown_value", f"'{key}' must be one of {allowed}"))
        return None


def _parse_key(raw: Mapping[str, Any], path: str, issues: list[Issue]) -> AnswerKeyCandidate | None:
    if "answer_key" not in raw or raw["answer_key"] is None:
        return None
    key_raw = raw["answer_key"]
    key_path = _join(path, "answer_key")
    if not isinstance(key_raw, Mapping):
        issues.append(Issue(key_path, "wrong_type", "'answer_key' must be an object"))
        return None
    status = _enum_text(key_raw, "status", KEY_STATUSES, key_path, issues)
    accepted = _str_list(key_raw, "accepted", key_path, issues)
    if status is None or accepted is None:
        return None
    normalized = tuple(_normalize(answer) for answer in accepted)
    if not normalized or len(set(normalized)) != len(normalized):
        issues.append(Issue(_join(key_path, "accepted"), "answer_key_invalid",
                            "accepted answers must be non-empty and unique after whitespace normalization"))
        return None
    return AnswerKeyCandidate(normalized, status)


def _parse_rubric(raw: Mapping[str, Any], path: str, issues: list[Issue]) -> RubricSpec | None:
    if "rubric" not in raw or raw["rubric"] is None:
        return None
    rubric_raw = raw["rubric"]
    rubric_path = _join(path, "rubric")
    if not isinstance(rubric_raw, Mapping):
        issues.append(Issue(rubric_path, "wrong_type", "'rubric' must be an object"))
        return None
    rubric_id = _field(rubric_raw, "id", str, rubric_path, issues)
    criteria: list[CriterionSpec] = []
    for index, criterion_raw in enumerate(_field(rubric_raw, "criteria", list, rubric_path, issues) or []):
        criterion_path = f"{rubric_path}.criteria[{index}]"
        if not isinstance(criterion_raw, Mapping):
            issues.append(Issue(criterion_path, "wrong_type", "each criterion must be an object"))
            continue
        criterion_id = _field(criterion_raw, "id", str, criterion_path, issues)
        description = _field(criterion_raw, "description", str, criterion_path, issues)
        if criterion_id is not None and description is not None:
            criteria.append(CriterionSpec(criterion_id, description))
    if rubric_id is None or not criteria:
        if rubric_id is not None:
            issues.append(Issue(rubric_path, "rubric_invalid", "a rubric needs at least one criterion"))
        return None
    if len({criterion.id for criterion in criteria}) != len(criteria):
        issues.append(Issue(rubric_path, "rubric_invalid", "criterion ids must be unique"))
        return None
    return RubricSpec(rubric_id, tuple(criteria))


def _parse_hints(raw: Mapping[str, Any], path: str, issues: list[Issue]) -> tuple[HintSpec, ...] | None:
    hints: list[HintSpec] = []
    for index, hint_raw in enumerate(_field(raw, "hints", list, path, issues) or []):
        hint_path = f"{_join(path, 'hints')}[{index}]"
        if not isinstance(hint_raw, Mapping):
            issues.append(Issue(hint_path, "wrong_type", "each hint must be an object"))
            return None
        level = _enum_value(hint_raw, "level", HintLevel, hint_path, issues)
        text = _field(hint_raw, "text", str, hint_path, issues)
        if level is None or text is None:
            return None
        hints.append(HintSpec(level, text))
    levels = tuple(hint.level for hint in hints)
    if levels != REQUIRED_HINT_LEVELS:
        issues.append(Issue(_join(path, "hints"), "hint_ladder",
                            "hints must be exactly nudge, targeted, worked_solution, in that order"))
        return None
    return tuple(hints)


def _check_sources(cited: tuple[str, ...], path: str, source_ids: set[str], issues: list[Issue]) -> None:
    if not cited:
        issues.append(Issue(_join(path, "source_ids"), "missing_source", "every lesson and item cites a source"))
    for source_id in cited:
        if source_id not in source_ids:
            issues.append(Issue(_join(path, "source_ids"), "unknown_reference", f"'{source_id}' is not a source"))


def _check_item_shape(activity_type: ActivityType, path: str, choices: tuple[str, ...],
                      key: AnswerKeyCandidate | None, check_expression: str | None,
                      rubric: RubricSpec | None, hints: tuple[HintSpec, ...], issues: list[Issue]) -> None:
    if activity_type in SCORED_TYPES:
        if key is None:
            issues.append(Issue(path, "answer_key_missing", "choice and trace items need a candidate answer key"))
        if rubric is not None:
            issues.append(Issue(path, "rubric_unexpected", "scored items are not rubric-reviewed"))
    else:
        if key is not None:
            issues.append(Issue(path, "ungraded_key", "explanation and code design items cannot have an answer key"))
        if rubric is None:
            issues.append(Issue(path, "rubric_missing", "ungraded items need a review rubric"))
        if check_expression is not None:
            issues.append(Issue(path, "check_unexpected", "only scored items take a check expression"))

    if activity_type is ActivityType.CHOICE:
        normalized_choices = tuple(_normalize(choice) for choice in choices)
        if len(normalized_choices) < 2 or len(set(normalized_choices)) != len(normalized_choices):
            issues.append(Issue(path, "choices_invalid", "choice items need at least two distinct choices"))
        elif key is not None and (len(key.accepted) != 1 or key.accepted[0] not in normalized_choices):
            issues.append(Issue(path, "choice_key_invalid", "a choice item needs exactly one correct listed choice"))
    elif choices:
        issues.append(Issue(path, "choices_unexpected", "only choice items may list choices"))

    if activity_type is ActivityType.TRACE and check_expression is None:
        issues.append(Issue(path, "check_missing",
                            "trace items need a check expression that the candidate key is verified against"))


def _check_coverage(concepts: list[Concept], lessons: list[Lesson], items: list[ItemContent],
                    issues: list[Issue]) -> None:
    for concept in concepts:
        where = f"concepts[{concept.id}]"
        if not any(lesson.concept_id == concept.id for lesson in lessons):
            issues.append(Issue(where, "coverage", "a concept needs at least one lesson"))
        concept_items = [item for item in items if item.activity.concept_id == concept.id]
        families = {item.activity.family_id for item in concept_items}
        if len(families) < MIN_FAMILIES_PER_CONCEPT:
            issues.append(Issue(where, "coverage",
                                f"a concept needs at least {MIN_FAMILIES_PER_CONCEPT} item families"))
        if not any(item.activity.activity_type in SCORED_TYPES for item in concept_items):
            issues.append(Issue(where, "coverage", "a concept needs at least one choice or trace item"))
        if not any(item.activity.held_out and item.activity.evidence_kind in HELD_OUT_EVIDENCE
                   for item in concept_items):
            issues.append(Issue(where, "coverage", "a concept needs a held-out application or transfer item"))


def _parse_receipts(data: Mapping[str, Any], issues: list[Issue]) -> list[ReviewReceipt] | None:
    review = _field(data, "review", dict, "", issues, required=False, default={})
    if review is None:
        return None
    receipts: list[ReviewReceipt] = []
    for index, raw in enumerate(_field(review, "receipts", list, "review", issues, required=False, default=[]) or []):
        path = f"review.receipts[{index}]"
        if not isinstance(raw, Mapping):
            issues.append(Issue(path, "wrong_type", "each receipt must be an object"))
            continue
        reviewer = _field(raw, "reviewer", str, path, issues)
        reviewed_on_text = _field(raw, "reviewed_on", str, path, issues)
        outcome = _enum_text(raw, "outcome", RECEIPT_OUTCOMES, path, issues)
        scope = _str_list(raw, "scope_ids", path, issues)
        reviewed_on = None
        if reviewed_on_text is not None:
            try:
                reviewed_on = date.fromisoformat(reviewed_on_text)
            except ValueError:
                issues.append(Issue(_join(path, "reviewed_on"), "wrong_type", "'reviewed_on' must be an ISO date"))
        if None in (reviewer, reviewed_on, outcome, scope):
            continue
        if not scope:
            issues.append(Issue(_join(path, "scope_ids"), "review_invalid", "a receipt must name what it covers"))
            continue
        receipts.append(ReviewReceipt(reviewer, reviewed_on, outcome, scope))
    return receipts


def _check_review(status: str, author: str, concepts: list[Concept], lessons: list[Lesson],
                  items: list[ItemContent], receipts: list[ReviewReceipt] | None,
                  issues: list[Issue]) -> None:
    receipts = receipts or []
    all_ids = {concept.id for concept in concepts} | {lesson.id for lesson in lessons} | {item.id for item in items}
    for receipt in receipts:
        if receipt.reviewer == author:
            issues.append(Issue("review.receipts", "review_invalid", "a reviewer cannot review their own pack"))
        for scope_id in receipt.scope_ids:
            if scope_id not in all_ids:
                issues.append(Issue("review.receipts", "unknown_reference", f"'{scope_id}' is not in this pack"))

    key_items = [item for item in items if item.answer_key is not None]
    if status != "reviewed":
        if any(item.answer_key.status == "reviewed" for item in key_items):
            issues.append(Issue("items", "review_claimed",
                                "keys can be marked reviewed only when the pack is reviewed"))
        return

    approved = {scope_id for receipt in receipts if receipt.outcome == "approved" for scope_id in receipt.scope_ids}
    for record_id in sorted(all_ids - approved):
        issues.append(Issue(record_id, "review_claimed", "a reviewed pack needs an approved receipt for every record"))
    for item in key_items:
        if item.answer_key.status != "reviewed":
            issues.append(Issue(item.id, "review_claimed", "a reviewed pack needs reviewed answer keys"))

# Micro-unit pack format

`micro-unit-pack/1` is a separate, strict JSON format. Existing `content-pack/1`
Python packs and their loader are unchanged. Import `load_micro_unit_pack`,
`parse_micro_unit_pack`, or `validate_micro_unit_pack` from
`aesop_lab.content.micro_unit`. Parsing returns frozen typed records; variants
are a read-only mapping. Validation returns the existing path/code/message
`Issue` records; parsing raises `ContentValidationError` containing all issues.
Unknown fields are rejected, including attempts to add extra checks or weights.

Short schema (all strings nonempty; all fields required unless marked optional):

```text
pack: {kind: "micro_unit", schema_version: "micro-unit-pack/1", pack_id,
       methods: [method, ...], units: [unit, ...]}
method: {id, name, description}
unit: {id, target: {word, gloss}, variants: {method_id: lesson_text, ...},
       check: check, practice?: [{id, prompt}, ...]}
check: {id, family_id, prompt,
        answer_key: {status: "candidate", accepted: [answer, ...]},
        check_delay_days: 7, held_out: true}
```

For example, one unit for a pack declaring only `cued_retrieval`:

```json
{
  "id": "voma",
  "target": {"word": "voma", "gloss": "river"},
  "variants": {"cued_retrieval": "voma means river. Cover the meaning and recall it."},
  "check": {
    "id": "voma-day7",
    "family_id": "voma-recall",
    "prompt": "Give the English meaning of voma.",
    "answer_key": {"status": "candidate", "accepted": ["river"]},
    "check_delay_days": 7,
    "held_out": true
  }
}
```

See `tests/fixtures/micro-unit-sample.json` for a complete pack with three
methods and four independent word targets. This is a format fixture, not a
reviewed teaching pack. The full intended method set also includes
`rule_then_drill`; method IDs are pack-declared, not a global enum.

Validation requires nonempty methods and units, unique method and unit IDs,
unique check family IDs across units, and unique item IDs across checks and
practice. Every declared method needs exactly one string variant per unit;
undeclared variants are rejected. A check must be one object, have a nonempty
candidate answer list, integer delay 7, and literal boolean `true` held-out.
Duplicate accepted strings are rejected. Practice is optional and never adds
units, checks, families, or weights.

Leak detection guards only the check prompt. Every accepted answer is matched
against its own check prompt as a whole word or phrase, ignoring case, so "me"
does not match "mean". Variants are not checked: a vocabulary lesson exists to
teach the answer, including accepted synonyms. For example, gloss "to borrow"
with the accepted answer "borrow" is legitimate in every variant. Integration
(Claude) removed an earlier variant rule, because it would have rejected exactly
such synonyms. This is not a semantic independence or paraphrase detector.
Independent review must still assess target independence and teaching quality.

Mapping to design #60's unit rules: the unit ID denotes one independent target,
not a method variant or practice item. A2 must select exactly one variant for
one exposure and assign exactly one day-7 check at weight 1. There is no
configurable weight, additional delayed-check list, scheduling, assignment,
content registration, or review approval in this format implementation.
Candidate keys do not claim independent review or authorize scoring.

A2 must decide the stable method IDs for production (including rule-then-drill),
assignment/balancing and exposure persistence, the meaning of day 7 relative to
exposure timestamps, candidate-key review/scoring gates, and how practice is
served without re-exposing held-out checks. Prefer an answer policy before
adding case or whitespace normalization. The referenced design and topic-decision
files were absent from this worktree; this mapping follows the supplied work order.

Validation tests live in `tests/test_micro_unit_content.py`. Each broken-fixture
test asserts a specific issue path/code and that parsing raises. Separate tests
cover allowed teaching reveals, typed loading, immutable variants, optional
practice, and collecting multiple issues.

## A1 verification

Required Python discovery passed: 311 tests. The final focused micro-unit suite
passed: 23 tests (including two additional malformed-input tests). The Node web
contract suite passed: 39 tests. Diagnostic
break checks temporarily suppressed the specific path/code from each of these
11 guards in memory: missing variant, unknown method, duplicate unit/family/check
IDs, missing key, non-candidate key, wrong delay, held-out flag, prompt leak,
and non-target variant leak. Every corresponding test failed: 11/11 detected.
Integration then replaced the variant-leak rule with whole-word, case-insensitive
prompt matching. Restoring the old substring rule fails the two new prompt tests.
The source files were not modified by those break checks. These checks verify
guard sensitivity; they do not establish semantic independence of the fixture.

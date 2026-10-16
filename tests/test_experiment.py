"""Protocol fixtures use a controlled clock; they are not human outcomes."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

from aesop_lab.domain.models import (
    Activity, ActivityType, Attempt, EvidenceKind, ExperimentAssignment,
    HintLevel, ScoreStatus,
)
from aesop_lab.experiment import (
    PROTOCOL, Exposure, analyze, assign_condition, qualifies_primary_outcome,
)


START = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
CONCEPT = "function-definition-and-return"
FAMILY = "def-return-shipping-week-v4"
CHECK = Activity("def-return-week-01", CONCEPT, "v4", FAMILY,
                 ActivityType.TRACE, EvidenceKind.APPLICATION, True, 7)
PRACTICE = Activity("def-return-practice-01", CONCEPT, "v4", "def-return-practice-a",
                    ActivityType.TRACE, EvidenceKind.APPLICATION)


def assignment(condition="text"):
    return ExperimentAssignment(PROTOCOL.id, PROTOCOL.version, CONCEPT, CONCEPT,
                                condition, PROTOCOL.seed, START)


def exposure(condition="text", *, families=(), completed=True):
    return Exposure(CONCEPT, "v4", condition, START, families,
                    completed_at=START if completed else None)


def attempt(*, activity=CHECK, when=START + timedelta(days=7),
            hint=HintLevel.NONE, score=ScoreStatus.CORRECT,
            grading_method="reviewed_exact_key", id="attempt-1"):
    return Attempt(id, activity.id, activity.content_version, when, "answer", hint,
                   score, grading_method, "assessment-v1", "fixed pilot item")


class ProtocolTests(unittest.TestCase):
    def test_fixed_protocol_exposes_complete_assignment_and_analysis_rules(self):
        public = PROTOCOL.public()
        self.assertEqual(public["primaryDelayDays"], 7)
        self.assertEqual(public["contentVersion"], "v4")
        self.assertIn("SHA-256", public["assignmentMethod"])
        self.assertFalse(public["exposureDurationControlled"])
        self.assertEqual(len(public["primaryFamilyByConcept"]), 5)
        self.assertEqual(public["primaryFamilyByConcept"]["base-case"],
                         "base-case-threshold-halving-week-v4")
        self.assertEqual(public["primaryFamilyByConcept"]["parameters-and-local-scope"],
                         "scope-combined-default-local-week-v4")
        self.assertEqual(public["primaryFamilyByConcept"]["function-definition-and-return"],
                         "def-return-shipping-week-v4")
        self.assertEqual(public["primaryFamilyByConcept"]["recursion-as-self-call"],
                         "recursion-return-order-week-v4")
        self.assertIn("missing", public["missingDataRule"].lower())
        self.assertIn("diagram", public["conditions"])

    def test_frozen_primary_families_match_v4_content_without_reuse_in_practice(self):
        path = (Path(__file__).resolve().parents[1] / "content" / "packs" /
                "python-functions-recursion" / "pack-m2-draft.4.json")
        pack = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(pack["pack_version"], "m2-draft.4")
        for concept_id, family_id in PROTOCOL.primary_family_by_concept:
            with self.subTest(concept_id=concept_id):
                matching = [item for item in pack["items"] if item["family_id"] == family_id]
                self.assertEqual(len(matching), 1)
                self.assertEqual(matching[0]["concept_id"], concept_id)
                self.assertTrue(matching[0]["held_out"])
                self.assertEqual(matching[0]["check_delay_days"], 7)

    def test_seeded_assignment_is_stable_and_does_not_depend_on_python_hash(self):
        first = assign_condition(CONCEPT, "learner-one")
        self.assertEqual(first, assign_condition(CONCEPT, "learner-one"))
        self.assertIn(first, ("text", "diagram"))
        choices = {assign_condition(cid, "learner-one") for cid in PROTOCOL.primary_families}
        self.assertEqual(choices, {"text", "diagram"})
        text_counts = {sum(assign_condition(cid, learner) == "text"
                           for cid in PROTOCOL.primary_families)
                       for learner in ("learner-one", "learner-three")}
        self.assertEqual(text_counts, {2, 3})
        with self.assertRaises(ValueError):
            assign_condition("unknown", "unknown")

    def test_exposure_rejects_version_and_temporal_mismatch(self):
        with self.assertRaisesRegex(ValueError, "content version"):
            Exposure(CONCEPT, "v3", "text", START, ())
        with self.assertRaisesRegex(ValueError, "precedes"):
            Exposure(CONCEPT, "v4", "text", START, (), completed_at=START - timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError, "unique"):
            Exposure(CONCEPT, "v4", "text", START, (FAMILY, FAMILY))

    def test_primary_requires_week_old_unfamiliar_unassisted_scored_first_response(self):
        self.assertTrue(qualifies_primary_outcome(
            attempt(), CHECK, exposure(), (), now=START + timedelta(days=8)))
        for observed in (
            attempt(when=START + timedelta(days=1)),
            attempt(when=START + timedelta(days=15)),
            attempt(hint=HintLevel.NUDGE),
            attempt(score=ScoreStatus.UNGRADED, grading_method="ungraded_pending_review"),
            attempt(grading_method="unsupported_heuristic"),
        ):
            with self.subTest(observed=observed):
                self.assertFalse(qualifies_primary_outcome(
                    observed, CHECK, exposure(), (), now=START + timedelta(days=16)))
        self.assertFalse(qualifies_primary_outcome(
            attempt(), CHECK, exposure(families=(FAMILY,)), (), now=START + timedelta(days=8)))
        self.assertFalse(qualifies_primary_outcome(
            attempt(), CHECK, exposure(), (FAMILY,), now=START + timedelta(days=8)))
        self.assertFalse(qualifies_primary_outcome(
            attempt(), CHECK, exposure(completed=False), (), now=START + timedelta(days=8)))
        self.assertFalse(qualifies_primary_outcome(
            attempt(), CHECK, exposure(), (), now=START + timedelta(days=6)))

    def test_analysis_keeps_missing_separate_from_incorrect_and_reports_uncertainty(self):
        result = analyze([assignment()], [exposure()], [attempt()],
                         {CHECK.id: CHECK}, now=START + timedelta(days=8))
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertEqual(result["contentReviewStatus"], "draft")
        self.assertIn("lack independent content review", result["reason"])
        self.assertEqual(result["arms"]["text"]["eligible"], 1)
        self.assertEqual(result["arms"]["text"]["correct"], 1)
        self.assertEqual(result["arms"]["text"]["missing"], 0)
        self.assertEqual(result["arms"]["diagram"]["correctRate"], None)
        self.assertIsNotNone(result["arms"]["text"]["interval95"])

        missing = analyze([assignment()], [exposure()], [], {}, now=START + timedelta(days=8))
        self.assertEqual(missing["arms"]["text"]["eligible"], 0)
        self.assertEqual(missing["arms"]["text"]["missing"], 1)
        wrong = analyze([assignment()], [exposure()], [attempt(score=ScoreStatus.INCORRECT)],
                        {CHECK.id: CHECK}, now=START + timedelta(days=8))
        self.assertEqual(wrong["arms"]["text"]["eligible"], 1)
        self.assertEqual(wrong["arms"]["text"]["correct"], 0)

    def test_review_status_must_be_explicit_before_descriptive_analysis(self):
        reviewed = analyze([assignment()], [exposure()], [attempt()],
                           {CHECK.id: CHECK}, now=START + timedelta(days=8),
                           content_review_status="reviewed")
        self.assertEqual(reviewed["status"], "insufficient_evidence")
        self.assertIn("not equivalently controlled", reviewed["reason"])
        with self.assertRaisesRegex(ValueError, "review status"):
            analyze([], [], [], {}, now=START, content_review_status="assumed")

    def test_first_primary_family_response_cannot_be_replaced_by_later_correct_answer(self):
        early = attempt(id="early", when=START + timedelta(days=1),
                        score=ScoreStatus.INCORRECT)
        later = attempt(id="later", when=START + timedelta(days=7))
        result = analyze([assignment()], [exposure()], [early, later],
                         {CHECK.id: CHECK}, now=START + timedelta(days=8))
        self.assertEqual(result["arms"]["text"]["eligible"], 0)
        self.assertEqual(result["arms"]["text"]["missing"], 1)

    def test_prior_practice_in_same_family_disqualifies_unfamiliar_outcome(self):
        leaked = Activity("leaked-practice", CONCEPT, "v4", FAMILY,
                          ActivityType.TRACE, EvidenceKind.APPLICATION)
        result = analyze([assignment()], [exposure()], [
            attempt(id="leaked", activity=leaked, when=START + timedelta(days=2)),
            attempt(id="week", when=START + timedelta(days=7))],
            {CHECK.id: CHECK, leaked.id: leaked}, now=START + timedelta(days=8))
        self.assertEqual(result["arms"]["text"]["eligible"], 0)
        self.assertEqual(result["arms"]["text"]["missing"], 1)

    def test_duplicate_exposure_is_rejected_instead_of_silently_replaced(self):
        with self.assertRaisesRegex(ValueError, "duplicate exposure"):
            analyze([assignment()], [exposure(), exposure()], [], {},
                    now=START + timedelta(days=8))


if __name__ == "__main__":
    unittest.main()

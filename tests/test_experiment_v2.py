"""Controlled fixtures validate v2 mechanics, not real human learning."""

from datetime import datetime, timedelta, timezone
import unittest

from aesop_lab.domain.models import (
    Activity, ActivityType, Attempt, EvidenceKind, ExperimentAssignment,
    HintLevel, ScoreStatus,
)
from aesop_lab.experiment import Exposure as V1Exposure, PROTOCOL as V1_PROTOCOL
from aesop_lab.experiment.descriptive_v2 import (
    DESCRIPTIVE_V2, ExposureV2, analyze_v2, assign_condition_v2, effect_policy_gate_v2,
)


START = datetime(2026, 10, 17, 12, tzinfo=timezone.utc)
LEARNER = "isolated-test-learner"
CONCEPT = "function-definition-and-return"
FAMILY = "def-return-shipping-week-v4"
ITEM = Activity("def-return-week-01-v5", CONCEPT, "v5", FAMILY,
                ActivityType.TRACE, EvidenceKind.APPLICATION, True, 7)


def assignment(concept=CONCEPT, learner=LEARNER):
    return ExperimentAssignment(
        DESCRIPTIVE_V2.id, DESCRIPTIVE_V2.version, concept, concept,
        assign_condition_v2(concept, learner), DESCRIPTIVE_V2.seed, START,
    )


def exposure(concept=CONCEPT, learner=LEARNER, **changes):
    fields = dict(concept_id=concept, content_version="v5",
                  condition_id=assign_condition_v2(concept, learner),
                  exposed_at=START, encountered_family_ids=(), completed_at=START)
    fields.update(changes)
    return ExposureV2(**fields)


def attempt(*, when=START + timedelta(days=7), status=ScoreStatus.CORRECT,
            hint=HintLevel.NONE, method="reviewed_exact_key", attempt_id="first"):
    return Attempt(attempt_id, ITEM.id, ITEM.content_version, when, "16", hint,
                   status, method, "assessment-v1", "held-out v2 check")


class DescriptiveV2Tests(unittest.TestCase):
    def test_v1_protocol_remains_unchanged_and_v2_is_new_version(self):
        self.assertEqual(V1_PROTOCOL.version, "v1")
        self.assertEqual(V1_PROTOCOL.seed, 20261015)
        self.assertEqual(DESCRIPTIVE_V2.version, "v2")
        self.assertNotEqual(DESCRIPTIVE_V2.seed, V1_PROTOCOL.seed)
        self.assertEqual(DESCRIPTIVE_V2.content_version, "v5")
        self.assertEqual(DESCRIPTIVE_V2.primary_families["recursion-as-self-call"],
                         "recursion-nested-wrap-week-v5")
        self.assertEqual(DESCRIPTIVE_V2.primary_families["parameters-and-local-scope"],
                         "scope-caller-local-default-week-v5")
        self.assertNotEqual(DESCRIPTIVE_V2.primary_families["parameters-and-local-scope"],
                            V1_PROTOCOL.primary_families["parameters-and-local-scope"])
        public = DESCRIPTIVE_V2.public()
        self.assertEqual(public["analysisUnit"], "independent_learner")
        self.assertEqual(public["targetExposureMinutes"], 10)
        self.assertFalse(public["exposureDurationControlled"])
        self.assertTrue(public["prospectiveOnly"])

    def test_assignment_is_deterministic_balanced_and_learner_specific(self):
        self.assertEqual(assign_condition_v2(CONCEPT, LEARNER),
                         assign_condition_v2(CONCEPT, LEARNER))
        for learner in ("alice", "bob", "charlie"):
            arms = [assign_condition_v2(concept, learner)
                    for concept in DESCRIPTIVE_V2.primary_families]
            self.assertEqual(set(arms), {"text", "diagram"})
            self.assertIn(arms.count("text"), (2, 3))
        with self.assertRaises(ValueError):
            assign_condition_v2("unknown", LEARNER)
        with self.assertRaises(ValueError):
            assign_condition_v2(CONCEPT, "")

    def test_exposure_duration_is_observed_only_and_validated(self):
        self.assertEqual(exposure(observed_seconds=600).observed_seconds, 600)
        with self.assertRaisesRegex(ValueError, "nonnegative"):
            exposure(observed_seconds=-1)
        with self.assertRaisesRegex(ValueError, "protocol"):
            exposure(protocol_version="v1")

    def test_one_learner_with_five_concept_outcomes_is_not_five_independent_units(self):
        assignments = [assignment(concept) for concept in DESCRIPTIVE_V2.primary_families]
        exposures = [exposure(concept) for concept in DESCRIPTIVE_V2.primary_families]
        activities = {}
        attempts = []
        for concept, family in DESCRIPTIVE_V2.primary_family_by_concept:
            item = Activity(f"{concept}-week", concept, "v5", family,
                            ActivityType.TRACE, EvidenceKind.APPLICATION, True, 7)
            activities[item.id] = item
            attempts.append(Attempt(f"{concept}-answer", item.id, "v5",
                                    START + timedelta(days=7), "answer", HintLevel.NONE,
                                    ScoreStatus.CORRECT, "reviewed_exact_key",
                                    "assessment-v1", "held-out v2 check"))
        result = analyze_v2(assignments, exposures, attempts, activities,
                            learner_id=LEARNER, now=START + timedelta(days=8),
                            content_review_status="reviewed")
        self.assertEqual(result["conceptObservationsTotal"], 5)
        self.assertEqual(result["independentLearnersTotal"], 1)
        self.assertEqual(result["independentLearnersWithOutcome"], 1)
        self.assertEqual(sum(a["independentLearners"] for a in result["arms"].values()), 2)
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertTrue(all(arm["interval95"] is None for arm in result["arms"].values()))

    def test_first_assisted_or_early_family_encounter_is_classified_separately(self):
        for first, classification in (
            (attempt(hint=HintLevel.NUDGE), "contaminated"),
            (attempt(when=START + timedelta(days=1)), "early"),
        ):
            with self.subTest(classification=classification):
                result = analyze_v2([assignment()], [exposure()],
                                    [first, attempt(attempt_id="later",
                                                    when=START + timedelta(days=8))],
                                    {ITEM.id: ITEM}, learner_id=LEARNER,
                                    now=START + timedelta(days=9))
                arm = result["arms"][assignment().condition_id]
                self.assertEqual(arm["eligible"], 0)
                self.assertEqual(arm[classification], 1)
                self.assertEqual(arm["missing"], 0)

    def test_ungraded_and_seen_family_do_not_count_but_incorrect_independent_does(self):
        reviewed = analyze_v2([assignment()], [exposure()],
                              [attempt(status=ScoreStatus.INCORRECT)],
                              {ITEM.id: ITEM}, learner_id=LEARNER,
                              now=START + timedelta(days=8),
                              content_review_status="reviewed")
        arm = reviewed["arms"][assignment().condition_id]
        self.assertEqual((arm["eligible"], arm["correct"], arm["missing"]), (1, 0, 0))
        self.assertEqual(reviewed["status"], "insufficient_evidence")
        self.assertIn("duration remains unverified", reviewed["reason"])
        ungraded = analyze_v2([assignment()], [exposure()],
                              [attempt(status=ScoreStatus.UNGRADED,
                                       method="ungraded_pending_review")],
                              {ITEM.id: ITEM}, learner_id=LEARNER,
                              now=START + timedelta(days=8))
        self.assertEqual(ungraded["arms"][assignment().condition_id]["ungraded"], 1)
        seen = analyze_v2([assignment()], [exposure(encountered_family_ids=(FAMILY,))],
                          [attempt()], {ITEM.id: ITEM}, learner_id=LEARNER,
                          now=START + timedelta(days=8))
        self.assertEqual(seen["arms"][assignment().condition_id]["eligible"], 0)
        self.assertEqual(seen["arms"][assignment().condition_id]["contaminated"], 1)

    def test_draft_candidate_match_is_provisional_and_never_primary_eligible(self):
        report = analyze_v2([assignment()], [exposure()],
                            [attempt(method="development_fixture_exact_key")],
                            {ITEM.id: ITEM}, learner_id=LEARNER,
                            now=START + timedelta(days=8))
        arm = report["arms"][assignment().condition_id]
        self.assertEqual((arm["provisional"], arm["candidateKeyMatches"]), (1, 1))
        self.assertEqual((arm["eligible"], arm["correct"], arm["independentLearners"]),
                         (0, 0, 0))
        self.assertEqual(report["conceptObservationsTotal"], 0)
        self.assertEqual(report["provisionalConceptObservationsTotal"], 1)
        self.assertEqual(arm["observations"][0]["candidateKeyStatus"], "correct")
        self.assertNotIn("reviewedScoreStatus", arm["observations"][0])
        reviewed = analyze_v2([assignment()], [exposure()],
                              [attempt(method="development_fixture_exact_key")],
                              {ITEM.id: ITEM}, learner_id=LEARNER,
                              now=START + timedelta(days=8),
                              content_review_status="reviewed")
        self.assertEqual(reviewed["arms"][assignment().condition_id]["ungraded"], 1)
        self.assertEqual(reviewed["arms"][assignment().condition_id]["eligible"], 0)

    def test_late_independent_first_response_keeps_actual_delay_outside_primary(self):
        delay = timedelta(days=17, hours=3, minutes=5, seconds=0.25)
        for review in ("draft", "reviewed"):
            with self.subTest(review=review):
                method = ("development_fixture_exact_key" if review == "draft"
                          else "reviewed_exact_key")
                late = attempt(when=START + delay, method=method)
                report = analyze_v2([assignment()], [exposure(observed_seconds=600)],
                                    [late], {ITEM.id: ITEM}, learner_id=LEARNER,
                                    now=late.occurred_at, content_review_status=review)
                arm = report["arms"][assignment().condition_id]
                self.assertEqual((arm["late"], arm["eligible"], arm["missing"]),
                                 (1, 0, 0))
                self.assertEqual(arm["exposureIncomparable"], 1)
                self.assertEqual(arm["observations"][0]["elapsedSeconds"],
                                 delay.total_seconds())
                self.assertEqual(arm["observations"][0]["classification"], "late")
                self.assertEqual(arm["observations"][0]["exposureComparability"],
                                 "unverified")
                self.assertEqual(report["lateConceptObservationsTotal"], 1)
                key = ("candidateKeyStatus" if review == "draft" else
                       "reviewedScoreStatus")
                self.assertEqual(arm["observations"][0][key], "correct")
                self.assertEqual(arm["lateCandidateKeyMatches" if review == "draft"
                                     else "lateReviewedCorrect"], 1)

    def test_preregistered_primary_window_boundaries_are_unchanged(self):
        cases = (
            (timedelta(days=7) - timedelta(microseconds=1), "early"),
            (timedelta(days=7), "eligible"),
            (timedelta(days=14), "eligible"),
            (timedelta(days=14) + timedelta(microseconds=1), "late"),
        )
        for delay, expected in cases:
            with self.subTest(delay=delay):
                first = attempt(when=START + delay)
                result = analyze_v2([assignment()], [exposure()], [first],
                                    {ITEM.id: ITEM}, learner_id=LEARNER,
                                    now=START + delay,
                                    content_review_status="reviewed")
                arm = result["arms"][assignment().condition_id]
                self.assertEqual(arm[expected], 1)
                self.assertEqual(arm["observations"][0]["classification"], expected)

    def test_missing_and_mismatched_exposure_are_not_silent_outcomes(self):
        no_attempt = analyze_v2([assignment()], [exposure()], [], {},
                                learner_id=LEARNER, now=START + timedelta(days=8))
        self.assertEqual(no_attempt["arms"][assignment().condition_id]["missing"], 1)
        wrong_start = exposure(exposed_at=START - timedelta(minutes=1),
                               completed_at=START)
        mismatch = analyze_v2([assignment()], [wrong_start], [attempt()],
                              {ITEM.id: ITEM}, learner_id=LEARNER,
                              now=START + timedelta(days=8))
        arm = mismatch["arms"][assignment().condition_id]
        self.assertEqual(arm["exposureIncomparable"], 1)
        self.assertEqual(arm["missing"], 0)
        self.assertEqual(arm["observations"][0]["classification"],
                         "exposure_incomparable")

    def test_foreign_assignment_and_wrong_learner_are_rejected(self):
        v1 = ExperimentAssignment(V1_PROTOCOL.id, V1_PROTOCOL.version, CONCEPT, CONCEPT,
                                  "text", V1_PROTOCOL.seed, START)
        with self.assertRaisesRegex(ValueError, "cannot be analyzed as v2"):
            analyze_v2([v1], [], [], {}, learner_id=LEARNER, now=START)
        old_exposure = V1Exposure(CONCEPT, "v4", "text", START, (), completed_at=START)
        with self.assertRaisesRegex(ValueError, "foreign exposure"):
            analyze_v2([], [old_exposure], [], {}, learner_id=LEARNER, now=START)
        # A mismatched learner may coincidentally receive the same arm, so
        # choose one with the opposite deterministic v2 assignment.
        other = next(f"other-{index}" for index in range(100)
                     if assign_condition_v2(CONCEPT, f"other-{index}") !=
                     assign_condition_v2(CONCEPT, LEARNER))
        with self.assertRaisesRegex(ValueError, "fixed v2 seed or learner"):
            analyze_v2([assignment()], [], [], {}, learner_id=other, now=START)

    def test_effect_gate_is_inactive_for_current_local_report(self):
        report = analyze_v2([assignment()], [exposure()], [attempt()],
                            {ITEM.id: ITEM}, learner_id=LEARNER,
                            now=START + timedelta(days=8))
        result = effect_policy_gate_v2(
            report, content_reviewed=True, exposure_verified=True,
            independent_learners_per_arm={"text": 20, "diagram": 20})
        self.assertFalse(result["eligible"])
        self.assertEqual(result["action"], "keep_current_policy")

    def test_effect_gate_only_invites_review_for_hypothetical_verified_cohort(self):
        # This synthetic object tests the gate, not human learning or a real
        # policy amendment. The gate changes no scheduler state.
        hypothetical = {
            "protocol": DESCRIPTIVE_V2.public(),
            "analysisUnit": "independent_learner",
            "status": "descriptive_only",
            "evidenceOrigin": "real_human_observations",
            "arms": {"text": {"independentLearners": 20},
                     "diagram": {"independentLearners": 20}},
        }
        counts = {"text": 20, "diagram": 20}
        ready = effect_policy_gate_v2(
            hypothetical, content_reviewed=True, exposure_verified=True,
            independent_learners_per_arm=counts)
        self.assertTrue(ready["eligible"])
        self.assertEqual(ready["action"], "request_independent_policy_review")
        self.assertIn("no causal method benefit", ready["reason"])
        for field, value in (("content_reviewed", False),
                             ("exposure_verified", False)):
            with self.subTest(field=field):
                args = dict(content_reviewed=True, exposure_verified=True,
                            independent_learners_per_arm=counts)
                args[field] = value
                self.assertFalse(effect_policy_gate_v2(hypothetical, **args)["eligible"])
        self.assertFalse(effect_policy_gate_v2(
            hypothetical, content_reviewed=True, exposure_verified=True,
            independent_learners_per_arm={"text": 19, "diagram": 20})["eligible"])
        hypothetical["evidenceOrigin"] = "synthetic_fixture"
        self.assertFalse(effect_policy_gate_v2(
            hypothetical, content_reviewed=True, exposure_verified=True,
            independent_learners_per_arm=counts)["eligible"])


if __name__ == "__main__":
    unittest.main()

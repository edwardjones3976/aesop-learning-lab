"""Outside-study exclusion follows the first explicit rule in protocol v5."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from importlib import import_module
import unittest

from aesop_lab.domain.models import (
    Activity, ActivityType, Attempt, EvidenceKind, ExperimentAssignment,
    HintLevel, OutsideStudy, ScoreStatus,
)


class DescriptiveOutsideStudyTests(unittest.TestCase):
    def check_response(self, version, outside_study, review, expected,
                       protocol_version=None, study_offset=None, other_concept=False):
        module = import_module(f"aesop_lab.experiment.descriptive_v{version}")
        protocol = getattr(module, f"DESCRIPTIVE_V{version}")
        start = datetime(2026, 10, 22, 12, tzinfo=timezone.utc)
        concept, family = protocol.primary_family_by_concept[0]
        learner = "outside-study-regression"
        condition = getattr(module, f"assign_condition_v{version}")(concept, learner)
        assignment = ExperimentAssignment(
            protocol.id, protocol.version, concept, concept, condition,
            protocol.seed, start,
        )
        exposure = getattr(module, f"ExposureV{version}")(
            concept, protocol.content_version, condition, start, (),
            completed_at=start,
        )
        activity = Activity("held-out", concept, protocol.content_version, family,
                            ActivityType.TRACE, EvidenceKind.APPLICATION, True, 7)
        first = Attempt(
            "first", activity.id, activity.content_version,
            start + timedelta(days=7), "answer", HintLevel.NONE,
            ScoreStatus.CORRECT,
            "reviewed_exact_key" if review == "reviewed" else "development_fixture_exact_key",
            "assessment-v1", "outside-study regression",
            outside_study=outside_study, outside_study_detail="Optional annotation",
        )
        if protocol_version is not None:
            from aesop_lab.experiment.descriptive_v2 import _classify_first

            classification, elapsed = _classify_first(
                first, activity, exposure, set(), first.occurred_at, review,
                replace(protocol, version=protocol_version),
            )
            self.assertEqual(classification, expected)
            self.assertIsNone(elapsed)
            return
        attempts = [first]
        activities = {activity.id: activity}
        if study_offset is not None:
            practice = replace(activity, id="practice", family_id="another-family",
                               concept_id=(protocol.primary_family_by_concept[1][0]
                                           if other_concept else concept),
                               held_out=False, check_delay_days=0)
            activities[practice.id] = practice
            attempts.append(replace(
                first, id="study-declaration", activity_id=practice.id,
                occurred_at=first.occurred_at + timedelta(seconds=study_offset),
                outside_study=OutsideStudy.SOME,
            ))
        report = getattr(module, f"analyze_v{version}")(
            [assignment], [exposure], attempts, activities,
            learner_id=learner, now=max(a.occurred_at for a in attempts),
            content_review_status=review,
        )
        arm = report["arms"][condition]
        self.assertEqual(arm["observations"][0]["classification"], expected)
        self.assertEqual(arm["observations"][0]["firstAttemptId"], first.id)
        self.assertEqual(arm[expected], 1)
        self.assertEqual(arm["missing"], 0)
        if expected == "contaminated":
            for field in ("eligible", "provisional", "correct", "candidateKeyMatches",
                          "independentLearners"):
                self.assertEqual(arm[field], 0)
            self.assertEqual(report["conceptObservationsTotal"], 0)
            self.assertEqual(report["provisionalConceptObservationsTotal"], 0)

    def test_reported_study_is_contaminated_from_v5(self):
        for version in (5, 6, 7):
            for review in ("draft", "reviewed"):
                with self.subTest(version=version, review=review):
                    self.check_response(version, OutsideStudy.SOME, review, "contaminated")

    def test_none_unknown_and_missing_do_not_report_study(self):
        for version in (5, 6, 7):
            for value in (OutsideStudy.NONE, OutsideStudy.UNKNOWN, None):
                for review in ("draft", "reviewed"):
                    with self.subTest(version=version, value=value, review=review):
                        expected = "eligible" if review == "reviewed" else "provisional"
                        self.check_response(version, value, review, expected)

    def test_earlier_protocol_classifications_remain_unchanged(self):
        for version in (2, 3, 4):
            for review in ("draft", "reviewed"):
                with self.subTest(version=version, review=review):
                    expected = "eligible" if review == "reviewed" else "provisional"
                    self.check_response(version, OutsideStudy.SOME, review, expected)

    def test_future_protocol_excludes_reported_study(self):
        for review in ("draft", "reviewed"):
            with self.subTest(review=review):
                self.check_response(7, OutsideStudy.SOME, review, "contaminated",
                                    protocol_version="v8")

    def test_malformed_protocol_version_fails_loudly(self):
        for version in ("", "8", "v", "v8.0", "v+8", "v8 "):
            with self.subTest(version=version):
                with self.assertRaisesRegex(ValueError, "protocol version"):
                    self.check_response(7, OutsideStudy.SOME, "draft", "contaminated",
                                        protocol_version=version)

    def test_prior_or_simultaneous_study_on_another_family_contaminates(self):
        for version in (5, 6, 7):
            for value in (OutsideStudy.NONE, OutsideStudy.UNKNOWN, None):
                for review in ("draft", "reviewed"):
                    for offset in (-60, 0):
                        with self.subTest(version=version, value=value,
                                          review=review, offset=offset):
                            self.check_response(version, value, review, "contaminated",
                                                study_offset=offset)

    def test_later_study_does_not_change_first_response(self):
        for version in (5, 6, 7):
            for review in ("draft", "reviewed"):
                with self.subTest(version=version, review=review):
                    self.check_response(
                        version, OutsideStudy.NONE, review,
                        "eligible" if review == "reviewed" else "provisional",
                        study_offset=60,
                    )

    def test_other_concept_study_does_not_contaminate(self):
        self.check_response(7, OutsideStudy.NONE, "draft", "provisional",
                            study_offset=-60, other_concept=True)

    def test_prior_study_preserves_frozen_protocols(self):
        for version in (2, 3, 4):
            with self.subTest(version=version):
                self.check_response(version, OutsideStudy.NONE, "draft", "provisional",
                                    study_offset=-60)

    def test_malformed_version_fails_before_assignment_or_empty_analysis(self):
        from aesop_lab.experiment.descriptive_v2 import DESCRIPTIVE_V2, _analyze

        for assignments in ([], [object()]):
            with self.subTest(assignments=bool(assignments)):
                with self.assertRaisesRegex(ValueError, "protocol version"):
                    protocol = replace(DESCRIPTIVE_V2, version="malformed")
                    _analyze(assignments, [], [], {}, learner_id="learner",
                             now=datetime.now(timezone.utc),
                             content_review_status="draft", protocol=protocol,
                             exposure_type=object)

"""Synthetic records test comparison mechanics, not human learning benefit."""

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from aesop_lab.api.personal_comparison import (
    CONTENT_VERSION, PROTOCOL_ID, UNIT_BY_ID, UNITS, PersonalComparison,
)
from aesop_lab.api.personal_comparison_v1 import (
    CONTENT_VERSION as V1_CONTENT_VERSION, PersonalComparison as LegacyPersonalComparison,
)
from aesop_lab.api.service import ApiError
from aesop_lab.foreman import Preview
from aesop_lab.storage.sqlite import SQLiteStore


START = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)


class PersonalComparisonTests(unittest.TestCase):
    def test_candidate_keys_and_held_out_structures(self):
        class Structure(ast.NodeTransformer):
            def visit_Name(self, node):
                return ast.copy_location(ast.Name(id="name", ctx=node.ctx), node)

            def visit_arg(self, node):
                node.arg = "name"
                return node

            def visit_Constant(self, node):
                return ast.copy_location(ast.Constant(value=0), node)

        shapes = []
        for unit in UNITS:
            for phase in ("worked", "practice", "delayed"):
                source = getattr(unit, f"{phase}_code")
                expected = getattr(unit, f"{phase}_answer")
                values = {}
                exec(compile(source, "<trusted comparison content>", "exec"),
                     {"__builtins__": {}}, values)
                result_name = ("result" if phase == "worked" and unit.pair == 1 else
                               "finish" if phase == "worked" else
                               "score" if phase == "practice" and unit.pair == 1 else
                               "end" if phase == "practice" else
                               "receipt" if unit.pair == 1 else "end")
                global_name = "bonus" if unit.pair == 1 else "step"
                self.assertEqual(f"{values[result_name]}, {values[global_name]}", expected)
                shape = ast.dump(Structure().visit(ast.parse(source)), include_attributes=False)
                shapes.append((unit.id, phase, shape))
        for unit_id, phase, shape in shapes:
            if phase == "practice":
                self.assertFalse(any(shape == other for other_id, other_phase, other in shapes
                                     if other_id == unit_id and other_phase == "worked"))
            if phase == "delayed":
                self.assertFalse(any(shape == other for _, other_phase, other in shapes
                                     if other_phase != "delayed"))
                self.assertFalse(any(shape == other for other_id, other_phase, other in shapes
                                     if other_phase == "delayed" and other_id != unit_id))
        for unit in UNITS:
            tree = ast.parse(unit.practice_code)
            func = next(node for node in tree.body if isinstance(node, ast.FunctionDef))
            if unit.pair == 1:
                self.assertTrue(any(isinstance(node, ast.If) for node in func.body))
            else:
                self.assertGreaterEqual(sum(isinstance(node, ast.Assign) for node in func.body), 2)

    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.db = Path(self.folder.name) / "comparison.sqlite3"
        self.clock = START
        self.store = SQLiteStore(self.db)
        self.store.confirm_consent(datetime.now(timezone.utc))
        self.addCleanup(lambda: self.store.close())
        self.comparison = PersonalComparison(self.store, lambda: self.clock,
                                             prior_concept_exposure=False)

    def test_balanced_persisted_assignment_and_first_answers(self):
        report = self.comparison.enroll()
        self.assertEqual([x["condition"] for x in report["units"]].count("diagram"), 2)
        self.assertEqual(report["status"], "insufficient_evidence")
        first = UNITS[0]
        self.comparison.start_exposure(first.id)
        self.comparison.complete_exposure(first.id, "none")
        exposed = self.comparison.report()["units"][0]["encounteredFamilyIds"]
        self.assertEqual(exposed, [first.family("worked")])
        self.comparison.open_question(first.id, "practice")
        self.assertEqual(self.comparison.report()["units"][0]["encounteredFamilyIds"],
                         [first.family("worked"), first.family("practice")])
        self.comparison.hint(first.id)
        result = self.comparison.answer(first.id, "practice", "0, 0")
        self.assertTrue(result["units"][0]["practiceAssisted"])
        self.assertFalse(result["units"][0]["practiceCandidateMatch"])
        with self.assertRaisesRegex(ValueError, "first answer is locked"):
            self.comparison.answer(first.id, "practice", first.practice_answer)
        self.store.close()
        self.store = SQLiteStore(self.db)
        self.store.confirm_consent(datetime.now(timezone.utc))
        self.comparison = PersonalComparison(self.store, lambda: self.clock,
                                             prior_concept_exposure=False)
        self.assertEqual(self.comparison.enroll()["units"][0]["condition"],
                         report["units"][0]["condition"])
        exported = self.store.export_all()
        self.assertEqual(len(exported["personalAssignments"]), 4)
        self.assertEqual(exported["personalResponses"][0]["first_answer"], "0, 0")
        self.assertEqual(exported["personalAssignments"][0]["content_version"], CONTENT_VERSION)

    def test_solution_opening_is_persisted_without_changing_first_answer(self):
        self.comparison.enroll()
        first = UNITS[0]
        with self.assertRaisesRegex(ValueError, "Unknown comparison unit"):
            self.comparison.reveal_solution([], "practice")
        self.comparison.start_exposure(first.id)
        self.comparison.complete_exposure(first.id, "none")
        self.comparison.open_question(first.id, "practice")
        with self.assertRaisesRegex(ValueError, "Submit the first answer"):
            self.comparison.reveal_solution(first.id, "practice")
        self.comparison.answer(first.id, "practice", "0, 0", "none")
        self.assertIsNone(self.comparison.report()["units"][0]["practiceSolutionRevealedAt"])
        self.assertIsNone(self.comparison.report()["feedback"]["answer"])
        self.assertEqual(self.comparison.report()["feedback"]["steps"], ())
        self.clock += timedelta(minutes=2)
        revealed = self.comparison.reveal_solution(first.id, "practice")
        at = revealed["units"][0]["practiceSolutionRevealedAt"]
        self.assertEqual(revealed["feedback"]["solutionRevealedAt"], at)
        self.assertEqual(revealed["feedback"]["answer"], first.practice_answer)
        self.assertEqual(revealed["feedback"]["steps"], first.practice_steps)
        self.clock += timedelta(minutes=1)
        self.assertEqual(self.comparison.reveal_solution(first.id, "practice")["units"][0]
                         ["practiceSolutionRevealedAt"], at)
        self.store.close()
        self.store = SQLiteStore(self.db)
        self.store.confirm_consent(datetime.now(timezone.utc))
        self.comparison = PersonalComparison(self.store, lambda: self.clock,
                                             prior_concept_exposure=False)
        self.assertEqual(self.comparison.report()["units"][0]["practiceSolutionRevealedAt"], at)
        exported = self.store.export_all()
        self.assertEqual(exported["personalResponses"][0]["first_answer"], "0, 0")
        self.assertEqual(len(exported["personalSolutionReveals"]), 1)
        self.store.delete_all()
        self.assertEqual(self.store.export_all()["personalSolutionReveals"], [])

    def test_two_hint_levels_persist_and_keep_first_response_assisted(self):
        self.comparison.enroll()
        first = UNITS[0]
        self.comparison.start_exposure(first.id)
        self.comparison.complete_exposure(first.id, "none")
        self.comparison.open_question(first.id, "practice")
        first_hint = self.comparison.hint(first.id)
        self.assertEqual(first_hint["level"], 1)
        self.assertTrue(first_hint["assisted"])
        self.assertTrue(self.comparison.report()["question"]["hintAvailable"])
        self.store.close()
        self.store = SQLiteStore(self.db)
        self.store.confirm_consent(datetime.now(timezone.utc))
        self.comparison = PersonalComparison(self.store, lambda: self.clock,
                                             prior_concept_exposure=False)
        self.assertEqual(self.comparison.report()["question"]["hintLevel"], 1)
        second_hint = self.comparison.hint(first.id)
        self.assertEqual(second_hint["level"], 2)
        self.assertNotEqual(first_hint["hint"], second_hint["hint"])
        self.assertFalse(self.comparison.report()["question"]["hintAvailable"])
        with self.assertRaisesRegex(ValueError, "All practice hints"):
            self.comparison.hint(first.id)
        answered = self.comparison.answer(first.id, "practice", first.practice_answer, "none")
        self.assertTrue(answered["units"][0]["practiceAssisted"])
        self.assertEqual([row["level"] for row in self.store.export_all()["personalHintEvents"]], [1, 2])
        self.store.delete_all()
        self.assertEqual(self.store.export_all()["personalHintEvents"], [])

    def test_both_conditions_delayed_and_contamination(self):
        self.comparison.enroll()
        for unit in UNITS:
            self.comparison.start_exposure(unit.id)
            self.comparison.complete_exposure(unit.id, "none")
            self.comparison.open_question(unit.id, "practice")
            self.comparison.answer(unit.id, "practice", unit.practice_answer)
        with self.assertRaisesRegex(ValueError, "not due"):
            self.comparison.open_question(UNITS[0].id, "delayed")
        self.clock += timedelta(days=8)
        for unit in UNITS:
            self.comparison.open_question(unit.id, "delayed")
            self.comparison.answer(unit.id, "delayed", unit.delayed_answer, "none")
        report = self.comparison.report()
        self.assertEqual(report["status"], "insufficient_evidence")
        self.assertEqual([u["classification"] for u in report["units"]], ["provisional"] * 4)
        self.assertTrue(all(u["actualDelayDays"] == 8 for u in report["units"]))
        for arm in ("text", "diagram"):
            self.assertEqual((report["arms"][arm]["eligible"], report["arms"][arm]["correct"],
                              report["arms"][arm]["provisional"]), (0, 0, 2))
            self.assertEqual(report["descriptive"][arm]["candidateMatches"], 2)
            self.assertEqual(report["descriptive"][arm]["eligibleCandidateMatches"], 0)
        self.assertEqual(report["descriptive"]["text"]["observed"], 2)
        self.assertEqual(report["descriptive"]["diagram"]["observed"], 2)
        self.assertEqual(report["dimensions"]["delayedRetention"]["observations"], 0)
        self.assertEqual(report["dimensions"]["delayedRetention"]["otherRecordedResponses"], 4)
        # A revealed held-out family is still preserved, but excluded.
        self.store.connection.execute(
            "UPDATE personal_exposures SET encountered_family_ids = ? WHERE unit_id = ?",
            ('["' + UNITS[0].family("delayed") + '"]', UNITS[0].id))
        self.store.connection.commit()
        self.assertEqual(self.comparison.report()["units"][0]["classification"], "contaminated")

    def test_human_reviewed_correct_delayed_answer_is_eligible(self):
        for module, comparison_type in (
                ("aesop_lab.api.personal_comparison", PersonalComparison),
                ("aesop_lab.api.personal_comparison_v1", LegacyPersonalComparison)):
            with self.subTest(protocol=comparison_type.__module__):
                self.store.delete_all()
                self.store.confirm_consent(START)
                self.clock = START
                comparison = comparison_type(self.store, lambda: self.clock,
                                             prior_concept_exposure=False)
                first = UNITS[0]
                with patch(f"{module}.CONTENT_REVIEW_STATUS", "human_reviewed"):
                    comparison.enroll()
                    comparison.start_exposure(first.id)
                    comparison.complete_exposure(first.id, "none")
                    comparison.open_question(first.id, "practice")
                    comparison.answer(first.id, "practice", first.practice_answer, "none")
                    self.clock += timedelta(days=8)
                    comparison.open_question(first.id, "delayed")
                    report = comparison.answer(first.id, "delayed",
                                               first.delayed_answer, "none")
                unit = report["units"][0]
                self.assertEqual(unit["classification"], "eligible")
                self.assertTrue(unit["delayedCandidateMatch"])
                self.assertEqual(report["arms"][unit["condition"]]["correct"], 1)

    def test_delayed_window_uses_unrounded_elapsed_time(self):
        self.comparison.enroll()
        for unit in UNITS[:2]:
            self.comparison.start_exposure(unit.id)
            self.comparison.complete_exposure(unit.id, "none")
            self.comparison.open_question(unit.id, "practice")
            self.comparison.answer(unit.id, "practice", unit.practice_answer)

        late, early = UNITS[:2]
        self.clock = START + timedelta(days=14, seconds=30)
        self.comparison.open_question(late.id, "delayed")
        self.comparison.answer(late.id, "delayed", late.delayed_answer, "none")

        # The public flow prevents early answers; restore a synthetic early record
        # to verify classification of persisted data at the precise boundary.
        self.clock = START + timedelta(days=7)
        self.comparison.open_question(early.id, "delayed")
        self.comparison.answer(early.id, "delayed", early.delayed_answer, "none")
        early_at = (START + timedelta(days=7, seconds=-30)).isoformat()
        with self.store.connection:
            self.store.connection.execute(
                "UPDATE personal_question_views SET first_viewed_at = ? WHERE unit_id = ? AND phase = 'delayed'",
                (early_at, early.id))
            self.store.connection.execute(
                "UPDATE personal_responses SET occurred_at = ? WHERE unit_id = ? AND phase = 'delayed'",
                (early_at, early.id))
        report = self.comparison.report()
        self.assertEqual([unit["classification"] for unit in report["units"][:2]],
                         ["late", "early"])
        self.assertGreater(report["units"][0]["actualDelayDays"], 14)
        self.assertLess(report["units"][1]["actualDelayDays"], 7)
        for unit in report["units"][:2]:
            self.assertEqual(report["arms"][unit["condition"]][unit["classification"]], 1)

    def test_prior_history_blocks_new_prospective_enrollment(self):
        comparison = PersonalComparison(self.store, lambda: self.clock,
                                        prior_concept_exposure=True)
        with self.assertRaisesRegex(ValueError, "prospective comparison"):
            comparison.enroll()
        self.assertEqual(self.store.connection.execute(
            "SELECT count(*) FROM personal_assignments WHERE protocol_id = ?",
            (PROTOCOL_ID,)).fetchone()[0], 0)

    def test_v1_assignment_and_response_remain_readable_and_block_v2(self):
        legacy = LegacyPersonalComparison(self.store, lambda: self.clock,
                                          prior_concept_exposure=False)
        legacy.enroll()
        legacy.start_exposure(UNITS[0].id)
        legacy.complete_exposure(UNITS[0].id, "none")
        legacy.open_question(UNITS[0].id, "practice")
        preview = Preview(self.db, now=lambda: self.clock)
        preview.consent()
        try:
            self.assertIsInstance(preview.personal_comparison(), LegacyPersonalComparison)
            with self.assertRaisesRegex(ApiError, "historical protocol version"):
                preview.reveal_comparison_solution(UNITS[0].id, "practice")
            preview.personal_comparison().answer(UNITS[0].id, "practice", "12, 40", "none", None)
        finally:
            preview.store.close()
        old = legacy.report()
        self.assertEqual(old["protocol"]["version"], "v1")
        self.assertEqual(old["protocol"]["contentVersion"], V1_CONTENT_VERSION)
        self.assertTrue(old["units"][0]["practiceCandidateMatch"])
        with self.assertRaisesRegex(ValueError, "another protocol version"):
            self.comparison.enroll()
        self.store.close()
        self.store = SQLiteStore(self.db)
        self.store.confirm_consent(datetime.now(timezone.utc))
        restored = LegacyPersonalComparison(self.store, lambda: self.clock,
                                            prior_concept_exposure=False)
        self.assertTrue(restored.report()["units"][0]["practiceCandidateMatch"])
        self.clock += timedelta(days=8)
        restored.open_question(UNITS[0].id, "delayed")
        legacy_result = restored.answer(UNITS[0].id, "delayed",
                                        UNITS[0].delayed_answer, "none")
        legacy_arm = legacy_result["units"][0]["condition"]
        self.assertEqual(legacy_result["units"][0]["classification"], "provisional")
        self.assertEqual((legacy_result["arms"][legacy_arm]["eligible"],
                          legacy_result["arms"][legacy_arm]["correct"]), (0, 0))
        self.assertEqual(legacy_result["descriptive"][legacy_arm]["candidateMatches"], 1)
        exported = self.store.export_all()
        self.assertEqual({row["protocol_version"] for row in exported["personalAssignments"]}, {"v1"})
        self.assertEqual(exported["personalResponses"][0]["content_version"], V1_CONTENT_VERSION)

    def test_due_check_preempts_new_unit_and_unknown_study_is_ineligible(self):
        self.comparison.enroll()
        first = UNITS[0]
        self.comparison.start_exposure(first.id)
        self.comparison.complete_exposure(first.id, "none")
        self.comparison.open_question(first.id, "practice")
        self.comparison.answer(first.id, "practice", first.practice_answer)
        self.clock += timedelta(days=8)
        self.assertEqual(self.comparison.report()["next"],
                         {"unitId": first.id, "stage": "delayed"})
        self.comparison.open_question(first.id, "delayed")
        self.comparison.answer(first.id, "delayed", first.delayed_answer)
        self.assertEqual(self.comparison.report()["units"][0]["classification"],
                         "outsideStudyUnknown")
        delayed_dimension = self.comparison.report()["dimensions"]["delayedRetention"]
        self.assertEqual(delayed_dimension["observations"], 0)
        self.assertEqual(delayed_dimension["otherRecordedResponses"], 1)
        self.assertEqual(delayed_dimension["status"], "insufficient_evidence")
        self.assertEqual(self.comparison.report()["next"],
                         {"unitId": UNITS[1].id, "stage": "study"})

    def test_versioned_recommendation_override_persists_without_changing_assignment(self):
        self.comparison.enroll()
        first, second = UNITS[:2]
        self.comparison.start_exposure(first.id)
        self.comparison.complete_exposure(first.id, "none")
        self.comparison.open_question(first.id, "practice")
        self.comparison.answer(first.id, "practice", "0, 0", "none", confidence=.75)
        self.assertEqual(self.comparison.report()["dimensions"]["confidenceCalibration"]["pairs"], 1)
        self.clock += timedelta(days=8)
        before = self.comparison.report()
        self.assertEqual(before["next"], {"unitId": first.id, "stage": "delayed"})
        recommendation = before["recommendation"]
        self.assertEqual(recommendation["alternative"],
                         {"unitId": second.id, "stage": "study"})
        self.assertTrue(recommendation["policyVersion"])
        with self.assertRaisesRegex(ValueError, "no longer available"):
            self.comparison.override(first.id, "delayed", UNITS[2].id, "study")
        chosen = self.comparison.override(first.id, "delayed", second.id, "study", "  ")
        self.assertEqual(chosen["next"], {"unitId": second.id, "stage": "study"})
        self.assertEqual(chosen["recommendation"], recommendation)
        self.assertIsNone(chosen["override"]["learnerReason"])
        exported = self.store.export_all()["personalRecommendationOverrides"]
        self.assertEqual(len(exported), 1)
        self.assertEqual(exported[0]["recommended_reason"], recommendation["reason"])
        self.assertEqual(exported[0]["policy_version"], recommendation["policyVersion"])
        with self.assertRaisesRegex(ValueError, "no longer available"):
            self.comparison.override(first.id, "delayed", second.id, "study")
        assigned = self.store.export_all()["personalAssignments"]
        self.store.close()
        self.store = SQLiteStore(self.db)
        self.store.confirm_consent(datetime.now(timezone.utc))
        self.comparison = PersonalComparison(self.store, lambda: self.clock,
                                             prior_concept_exposure=False)
        self.assertEqual(self.comparison.report()["next"],
                         {"unitId": second.id, "stage": "study"})
        self.assertEqual(self.store.export_all()["personalAssignments"], assigned)
        self.comparison.start_exposure(second.id)
        self.comparison.complete_exposure(second.id, "none")
        self.assertEqual(self.comparison.report()["next"],
                         {"unitId": second.id, "stage": "practice"})
        self.assertEqual(self.comparison.report()["override"]["originalSelectedStage"], "study")
        self.comparison.open_question(second.id, "practice")
        self.comparison.answer(second.id, "practice", second.practice_answer, "none")
        self.assertEqual(self.comparison.report()["next"],
                         {"unitId": first.id, "stage": "delayed"})
        self.assertIsNone(self.comparison.report()["override"])

    def test_dimensional_report_does_not_infer_unmeasured_skills(self):
        self.comparison.enroll()
        dimensions = self.comparison.report()["dimensions"]
        self.assertEqual(dimensions["explanation"]["status"], "not_measured")
        self.assertEqual(dimensions["transfer"]["status"], "not_measured")
        self.assertEqual(dimensions["studyTimeSustainability"]["status"], "not_measured")
        self.assertEqual(dimensions["confidenceCalibration"]["status"], "missing")

    def test_delayed_view_interruption_contaminates_response(self):
        self.comparison.enroll()
        first = UNIT_BY_ID[UNITS[0].id]
        self.comparison.start_exposure(first.id)
        self.comparison.complete_exposure(first.id, "none")
        self.comparison.open_question(first.id, "practice")
        self.comparison.answer(first.id, "practice", first.practice_answer)
        self.clock += timedelta(days=8)
        self.comparison.open_question(first.id, "delayed")
        viewed = self.comparison.report()["units"][0]["delayedFirstViewedAt"]
        self.clock += timedelta(minutes=31)
        self.comparison.answer(first.id, "delayed", first.delayed_answer, "none")
        result = self.comparison.report()["units"][0]
        self.assertEqual(result["delayedFirstViewedAt"], viewed)
        self.assertEqual(result["classification"], "contaminated")
        delayed_dimension = self.comparison.report()["dimensions"]["delayedRetention"]
        self.assertEqual(delayed_dimension["observations"], 0)
        self.assertEqual(delayed_dimension["otherRecordedResponses"], 1)

    def test_opening_standard_lesson_after_enrollment_contaminates_delayed_check(self):
        self.comparison.enroll()
        first = UNITS[0]
        self.comparison.start_exposure(first.id)
        self.comparison.complete_exposure(first.id, "none")
        self.comparison.open_question(first.id, "practice")
        self.comparison.answer(first.id, "practice", first.practice_answer)
        self.clock += timedelta(days=2)
        with self.store.connection:
            self.store.connection.execute(
                "INSERT INTO experiment_exposures VALUES (?, ?, ?, ?, ?, ?, NULL, ?)",
                ("parameters-and-local-scope", "v7", "text-vs-labeled-diagram", "v4",
                 "text", self.clock.isoformat(), "[]"))
        self.clock += timedelta(days=6)
        self.comparison.open_question(first.id, "delayed")
        self.comparison.answer(first.id, "delayed", first.delayed_answer, "none")
        row = self.comparison.report()["units"][0]
        self.assertTrue(row["otherConceptLearningBeforeDelayed"])
        self.assertEqual(row["classification"], "contaminated")


if __name__ == "__main__":
    unittest.main()

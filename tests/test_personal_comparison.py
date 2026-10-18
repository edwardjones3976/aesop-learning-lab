"""Synthetic records test comparison mechanics, not human learning benefit."""

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from aesop_lab.api.personal_comparison import (
    CONTENT_VERSION, PROTOCOL_ID, UNIT_BY_ID, UNITS, PersonalComparison,
)
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
            if phase == "delayed":
                self.assertFalse(any(shape == other for _, other_phase, other in shapes
                                     if other_phase != "delayed"))
                self.assertFalse(any(shape == other for other_id, other_phase, other in shapes
                                     if other_phase == "delayed" and other_id != unit_id))

    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.db = Path(self.folder.name) / "comparison.sqlite3"
        self.clock = START
        self.store = SQLiteStore(self.db)
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
        self.comparison = PersonalComparison(self.store, lambda: self.clock,
                                             prior_concept_exposure=False)
        self.assertEqual(self.comparison.enroll()["units"][0]["condition"],
                         report["units"][0]["condition"])
        exported = self.store.export_all()
        self.assertEqual(len(exported["personalAssignments"]), 4)
        self.assertEqual(exported["personalResponses"][0]["first_answer"], "0, 0")
        self.assertEqual(exported["personalAssignments"][0]["content_version"], CONTENT_VERSION)

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
        self.assertEqual([u["classification"] for u in report["units"]], ["eligible"] * 4)
        self.assertTrue(all(u["actualDelayDays"] == 8 for u in report["units"]))
        self.assertEqual(report["descriptive"]["text"]["observed"], 2)
        self.assertEqual(report["descriptive"]["diagram"]["observed"], 2)
        # A revealed held-out family is still preserved, but excluded.
        self.store.connection.execute(
            "UPDATE personal_exposures SET encountered_family_ids = ? WHERE unit_id = ?",
            ('["' + UNITS[0].family("delayed") + '"]', UNITS[0].id))
        self.store.connection.commit()
        self.assertEqual(self.comparison.report()["units"][0]["classification"], "contaminated")

    def test_prior_history_blocks_new_prospective_enrollment(self):
        comparison = PersonalComparison(self.store, lambda: self.clock,
                                        prior_concept_exposure=True)
        with self.assertRaisesRegex(ValueError, "prospective comparison"):
            comparison.enroll()
        self.assertEqual(self.store.connection.execute(
            "SELECT count(*) FROM personal_assignments WHERE protocol_id = ?",
            (PROTOCOL_ID,)).fetchone()[0], 0)

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
        self.assertEqual(self.comparison.report()["next"],
                         {"unitId": UNITS[1].id, "stage": "study"})

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

"""Bounded synthetic software validation of content m2-draft.11 under protocol v8.

Forty synthetic learners, each in its own temporary database, walk seven scripted
paths through the real Preview API. Antigravity wrote the first version; Codex
corrected the timing and assignments; Claude integrated it.

CRITICAL DISCLAIMER:
THIS IS NOT A REAL LEARNER SESSION.
SYNTHETIC OUTCOMES MUST NEVER BE REPORTED AS HUMAN LEARNING OR HUMAN RETENTION.
THIS TEST VALIDATES SOFTWARE MECHANICS ONLY.
"""

from collections import Counter
from datetime import datetime, timedelta, timezone
import gc
import json
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from aesop_lab.content import load_pack
from aesop_lab.domain.models import Attempt, HintLevel, ScoreStatus
from aesop_lab.experiment.descriptive_v8 import DESCRIPTIVE_V8, assign_condition_v8
from aesop_lab.foreman import CURRENT_PACK_PATH, Preview
from aesop_lab.storage.sqlite import SQLiteStore


NOW_BASE = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)
CONCEPTS = (
    "function-definition-and-return",
    "parameters-and-local-scope",
    "recursion-as-self-call",
    "base-case",
    "recursive-case-and-trace",
)


def expected_classification(i: int) -> str:
    """The primary-outcome classification each scripted path must produce (draft keys)."""
    if i < 14:
        return "provisional"  # paths 0 and 1: on time and unassisted, right or wrong
    if i < 20:
        return "contaminated"  # path 2: hint opened before submitting
    if i < 26:
        return "missing"  # path 3: window closed with no answer
    if i < 32:
        return "contaminated"  # path 4: outside study reported
    if i < 36:
        return "early"  # path 5: injected before day 7
    return "late"  # path 6: answered after day 14


class SyntheticV8CohortValidationTests(unittest.TestCase):
    """Executes bounded synthetic validation over 40 isolated temporary SQLite databases."""

    def test_forty_synthetic_learner_databases_validation(self):
        pack = load_pack(CURRENT_PACK_PATH)
        self.assertEqual(pack.pack_version, "m2-draft.11")
        self.assertEqual(pack.status, "draft")
        self.assertEqual(DESCRIPTIVE_V8.version, "v8")
        self.assertEqual(DESCRIPTIVE_V8.content_version, "v11")

        item_map = {item.id: item for item in pack.items}

        total_simulations = 40
        temp_paths = []
        arm_assignment_counts = Counter()
        primary_outcomes_by_arm = {
            "text": Counter(),
            "diagram": Counter(),
        }
        all_classifications = Counter()
        override_provenance_verified = 0
        persistence_verified = 0
        insufficient_evidence_verified = 0

        # Distribution plan for the 40 synthetic learners across varied paths:
        # Paths:
        # 0: i in [0..7]   (8): unassisted correct, day-1 return practice/transfer + day-7 return primary
        # 1: i in [8..13]  (6): wrong answer on primary check
        # 2: i in [14..19] (6): assisted (hint requested before submit) on primary check -> contaminated
        # 3: i in [20..25] (6): missing primary check after the day-14 window closes
        # 4: i in [26..31] (6): outside study reported on day-7 check -> contaminated
        # 5: i in [32..35] (4): deliberately injected early record to probe classifier -> early
        # 6: i in [36..39] (4): late check (>14 days, e.g. 15.5 days) -> late

        for i in range(total_simulations):
            td = tempfile.TemporaryDirectory()
            db_path = Path(td.name) / f"synthetic_learner_{i:03d}.db"
            temp_paths.append((td, db_path))

            t0 = NOW_BASE + timedelta(hours=i * 2)
            current_clock = [t0]

            preview = Preview(db_path, now=lambda: current_clock[0])
            self.assertEqual(preview.pack.pack_version, "m2-draft.11")

            # Validate that before any learner identity, status is insufficient_evidence
            self.assertIsNone(preview.store.existing_learner_id())
            initial_findings = preview.experiment_findings()
            self.assertEqual(initial_findings["status"], "insufficient_evidence")

            # Select target concept for this learner
            concept_id = CONCEPTS[i % len(CONCEPTS)]
            target_arm = "text" if i % 2 == 0 else "diagram"
            learner_id = next(
                f"synthetic-v11-{i:03d}-{candidate}"
                for candidate in range(100)
                if assign_condition_v8(concept_id, f"synthetic-v11-{i:03d}-{candidate}") == target_arm
            )
            with preview.store.connection:
                preview.store.connection.execute(
                    "INSERT INTO learner_identity (slot, id) VALUES (1, ?)",
                    (learner_id,),
                )
            assigned_arm = assign_condition_v8(concept_id, preview.store.learner_id())
            self.assertEqual(assigned_arm, target_arm)
            arm_assignment_counts[assigned_arm] += 1

            # Complete lesson (records exposure)
            lesson_res = preview.lesson(concept_id)
            self.assertEqual(lesson_res["method"]["conditionId"], assigned_arm)
            self.assertEqual(lesson_res["method"]["protocolVersion"], "v8")
            self.assertEqual(bool(lesson_res["diagram"]), assigned_arm == "diagram")
            preview.complete_lesson(concept_id)

            # Record and verify recommendation override provenance
            displayed_path = preview.overview()["pathRecommendation"]
            override_res = preview.override({
                "conceptId": concept_id,
                "mode": "practice",
                "reason": "learner_choice",
                "learnerReason": f"Synthetic override note {i}",
            })
            self.assertTrue(override_res["saved"])

            latest_override = preview.store.export_all()["recommendationOverrides"][-1]
            self.assertEqual(latest_override["learner_reason"], f"Synthetic override note {i}")
            self.assertEqual(latest_override["recommended_concept_id"], displayed_path["conceptId"])
            self.assertEqual(latest_override["recommended_action"], displayed_path["action"])
            self.assertEqual(latest_override["recommended_reason"], displayed_path["reason"])
            self.assertEqual(latest_override["selected_concept_id"], concept_id)
            override_provenance_verified += 1

            # Day 0 immediate retrieval practice
            session_d0 = preview.session(concept_id, mode="practice")
            d0_item = session_d0["activity"]
            d0_did = str(uuid4())
            ans0 = item_map[d0_item["id"]].answer_key.accepted[0]
            preview.first_answer({
                "conceptId": concept_id,
                "activityId": d0_item["id"],
                "draftId": d0_did,
                "answer": ans0,
            })
            preview.submit({"draftId": d0_did, "outsideStudy": "none"})

            # Day 1 return: advance clock to day 1 (+26 hours)
            current_clock[0] += timedelta(days=1, hours=2)
            session_d1 = preview.session(concept_id, mode="recommended")
            d1_item = session_d1.get("activity")
            if d1_item and d1_item["checkDelayDays"] == 1:
                # Answer day 1 check
                d1_did = str(uuid4())
                ans1 = item_map[d1_item["id"]].answer_key.accepted[0]
                preview.first_answer({
                    "conceptId": concept_id,
                    "activityId": d1_item["id"],
                    "draftId": d1_did,
                    "answer": ans1,
                })
                preview.submit({"draftId": d1_did, "outsideStudy": "none"})

            # Execute varied branch for day 7 / primary check
            primary_family = DESCRIPTIVE_V8.primary_families[concept_id]
            primary_pack_item = next(
                item for item in pack.items
                if item.activity.concept_id == concept_id and item.activity.family_id == primary_family
            )
            correct_key = primary_pack_item.answer_key.accepted[0]

            if i < 8:
                # Path 0: Day 7 return unassisted correct
                current_clock[0] = t0 + timedelta(days=7, hours=2)
                session_d7 = preview.session(concept_id, mode="recommended")
                d7_item = session_d7["activity"]
                self.assertEqual(d7_item["familyId"], primary_family)
                d7_did = str(uuid4())
                preview.first_answer({
                    "conceptId": concept_id,
                    "activityId": d7_item["id"],
                    "draftId": d7_did,
                    "answer": correct_key,
                })
                preview.submit({"draftId": d7_did, "outsideStudy": "none"})

            elif i < 14:
                # Path 1: Day 7 return wrong answer
                current_clock[0] = t0 + timedelta(days=7, hours=3)
                session_d7 = preview.session(concept_id, mode="recommended")
                d7_item = session_d7["activity"]
                self.assertEqual(d7_item["familyId"], primary_family)
                d7_did = str(uuid4())
                # If multiple choices, pick an incorrect choice; else an incorrect string
                wrong_answer = (
                    next(c for c in primary_pack_item.choices if c != correct_key)
                    if primary_pack_item.choices
                    else "definitely_wrong_answer_synthetic"
                )
                preview.first_answer({
                    "conceptId": concept_id,
                    "activityId": d7_item["id"],
                    "draftId": d7_did,
                    "answer": wrong_answer,
                })
                preview.submit({"draftId": d7_did, "outsideStudy": "none"})

            elif i < 20:
                # Path 2: Day 7 return assisted with hints -> contaminated
                current_clock[0] = t0 + timedelta(days=7, hours=4)
                session_d7 = preview.session(concept_id, mode="recommended")
                d7_item = session_d7["activity"]
                self.assertEqual(d7_item["familyId"], primary_family)
                d7_did = str(uuid4())
                preview.first_answer({
                    "conceptId": concept_id,
                    "activityId": d7_item["id"],
                    "draftId": d7_did,
                    "answer": correct_key,
                })
                preview.hint({"draftId": d7_did})
                preview.submit({"draftId": d7_did, "outsideStudy": "none"})

            elif i < 26:
                # Path 3: Missing primary check after its day-14 window closes.
                current_clock[0] = t0 + timedelta(days=15)
                # No attempt submitted for primary check

            elif i < 32:
                # Path 4: Day 7 return with outside study declared -> contaminated
                current_clock[0] = t0 + timedelta(days=7, hours=5)
                session_d7 = preview.session(concept_id, mode="recommended")
                d7_item = session_d7["activity"]
                self.assertEqual(d7_item["familyId"], primary_family)
                d7_did = str(uuid4())
                preview.first_answer({
                    "conceptId": concept_id,
                    "activityId": d7_item["id"],
                    "draftId": d7_did,
                    "answer": correct_key,
                })
                preview.submit({"draftId": d7_did, "outsideStudy": "some", "outsideStudyDetail": "synthetic outside textbook"})

            elif i < 36:
                # Path 5: Direct storage injection probes classifier behavior.
                # The learner-facing scheduler does not normally offer this item early.
                current_clock[0] = t0 + timedelta(days=1, hours=4)
                did_early = str(uuid4())
                preview.store.append_attempt(
                    Attempt(
                        did_early,
                        primary_pack_item.id,
                        primary_pack_item.activity.content_version,
                        current_clock[0],
                        correct_key,
                        HintLevel.NONE,
                        ScoreStatus.CORRECT,
                        "reviewed_exact_key",
                        "assessment-v1",
                        "synthetic early check",
                    )
                )

            else:
                # Path 6: Late return (> 14 days, e.g. 15.5 days)
                current_clock[0] = t0 + timedelta(days=15, hours=12)
                session_d7 = preview.session(concept_id, mode="recommended")
                d7_item = session_d7["activity"]
                self.assertEqual(d7_item["familyId"], primary_family)
                d7_did = str(uuid4())
                preview.first_answer({
                    "conceptId": concept_id,
                    "activityId": d7_item["id"],
                    "draftId": d7_did,
                    "answer": correct_key,
                })
                preview.submit({"draftId": d7_did, "outsideStudy": "none"})

            # Verify held-out family non-exposure during study:
            # The exposure encountered_family_ids must not include the primary held-out family
            recorded_exposures = preview.store.list_exposures()
            self.assertEqual(len(recorded_exposures), 1)
            exposure_families = tuple(json.loads(recorded_exposures[0]["encountered_family_ids"]))
            self.assertNotIn(primary_family, exposure_families)

            # Analyze findings
            findings = preview.experiment_findings()
            self.assertEqual(findings["status"], "insufficient_evidence")
            self.assertIn("minimum of 20 independent learners", findings["reason"])
            self.assertFalse(findings["syntheticResultsAreLearningEvidence"])
            insufficient_evidence_verified += 1

            # Determine observed classification for this arm
            arm_data = findings["arms"][assigned_arm]
            obs = next((o for o in arm_data["observations"] if o["conceptId"] == concept_id), None)
            self.assertIsNotNone(obs)
            classification = obs["classification"]
            self.assertEqual(classification, expected_classification(i), f"synthetic learner {i}")
            all_classifications[classification] += 1
            primary_outcomes_by_arm[assigned_arm][classification] += 1

            # Verify actual elapsed delay matches controlled clock
            if "elapsedSeconds" in obs:
                expected_elapsed = (current_clock[0] - t0).total_seconds()
                self.assertAlmostEqual(obs["elapsedSeconds"], expected_elapsed, delta=1.0)

            # Close preview and services to release SQLite locks
            for s in preview.services.values():
                s.store.close()
            preview.store.close()

            # Verify persistence after restart
            with SQLiteStore(db_path) as reopened:
                reopened_assignments = reopened.list_assignments(DESCRIPTIVE_V8.id)
                self.assertEqual(len(reopened_assignments), 1)
                self.assertEqual(reopened_assignments[0].condition_id, assigned_arm)
                self.assertEqual(len(reopened.list_exposures()), 1)
                reopened_overrides = reopened.export_all()["recommendationOverrides"]
                self.assertEqual(len(reopened_overrides), 1)
                self.assertEqual(reopened_overrides[0]["learner_reason"], f"Synthetic override note {i}")
            persistence_verified += 1

        # Summary assertions
        self.assertEqual(total_simulations, 40)
        self.assertEqual(sum(arm_assignment_counts.values()), 40)
        self.assertEqual(arm_assignment_counts, {"text": 20, "diagram": 20})

        # Confirm all varied classifications were covered
        self.assertGreater(all_classifications["provisional"], 0)
        self.assertGreater(all_classifications["contaminated"], 0)
        self.assertGreater(all_classifications["missing"], 0)
        self.assertGreater(all_classifications["early"], 0)
        self.assertGreater(all_classifications["late"], 0)

        self.assertEqual(override_provenance_verified, 40)
        self.assertEqual(persistence_verified, 40)
        self.assertEqual(insufficient_evidence_verified, 40)

        # Confirm every single temporary database directory is cleaned up
        gc.collect()
        for td, db_path in temp_paths:
            self.assertTrue(db_path.exists())
            td.cleanup()
            self.assertFalse(db_path.exists())


if __name__ == "__main__":
    unittest.main()

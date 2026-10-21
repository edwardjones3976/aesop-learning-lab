"""Tests for structural similarity guard on held-out evaluation items."""

import copy
import json
from pathlib import Path
import unittest

from aesop_lab.foreman import CURRENT_PACK_PATH
from tests.heldout_similarity import (
    compute_code_signature,
    find_heldout_similarity_flags,
)


# Documented allowlist for held-out items whose shape matches studied sources.
# Each entry MUST have an explicit, justified reason.
# If an item on this allowlist ceases to be flagged, CI must fail (stale allowlist guard).
CURRENT_PACK_ALLOWLIST = {
    "recursion-halving-transfer-01-v9": (
        "Judged near-transfer on day 1 (family recursion-halving-transfer-a, leaf_count). "
        "Structurally matches single-decrement multiplication recursion (base-case-trace-01-v9 / f(n)), "
        "evaluating tree branching rather than factorial."
    ),
}


class HeldoutSimilarityTests(unittest.TestCase):
    """Structural similarity guard tests."""

    @classmethod
    def setUpClass(cls):
        with open(CURRENT_PACK_PATH, "r", encoding="utf-8") as f:
            cls.current_pack = json.load(f)

        v10_path = Path(CURRENT_PACK_PATH).parent / "pack-m2-draft.10.json"
        with open(v10_path, "r", encoding="utf-8") as f:
            cls.v10_pack = json.load(f)

    def test_historical_regression_v10_nest_flagged_against_repeat_mark(self):
        """Historical regression fixture: in v10, recursion-week-01-v9 (nest)

        must be flagged against recursion-application-v9 (repeat_mark).
        """
        flags = find_heldout_similarity_flags(self.v10_pack)
        flagged_items = {f["held_out_id"]: f for f in flags}

        self.assertIn(
            "recursion-week-01-v9",
            flagged_items,
            "Historical regression failed: recursion-week-01-v9 (nest) was not flagged in v10 pack.",
        )

        nest_flag = flagged_items["recursion-week-01-v9"]
        matched_source_ids = {s["id"] for s in nest_flag["matched_sources"]}
        self.assertIn(
            "recursion-application-v9",
            matched_source_ids,
            f"recursion-week-01-v9 should match recursion-application-v9 (repeat_mark), matched: {matched_source_ids}",
        )

    def test_current_pack_ci_check_with_allowlist_and_stale_detection(self):
        """Current pack CI check: no held-out item is flagged unless it is on an ALLOWLIST.

        Each allowlist entry must have a written reason, and stale entries must fail.
        """
        flags = find_heldout_similarity_flags(self.current_pack)
        flagged_by_id = {f["held_out_id"]: f for f in flags}

        # 1. Stale allowlist check: every item in allowlist must actually be flagged
        for allowed_id, reason in CURRENT_PACK_ALLOWLIST.items():
            self.assertTrue(bool(reason and reason.strip()), f"Allowlist entry {allowed_id} has no written reason.")
            self.assertIn(
                allowed_id,
                flagged_by_id,
                f"Stale allowlist entry: {allowed_id} is on the allowlist but is no longer flagged!",
            )

        # 2. CI violation check: any flag not on allowlist fails CI
        unallowed_flags = [f for f in flags if f["held_out_id"] not in CURRENT_PACK_ALLOWLIST]
        self.assertEqual(
            unallowed_flags,
            [],
            f"Unallowed similarity flags found in current pack: {unallowed_flags}",
        )

    def test_v11_meet_is_not_flagged(self):
        """recursion-week-01-v11 (meet) has converging two-parameter recursion

        and must not be flagged against any source.
        """
        flags = find_heldout_similarity_flags(self.current_pack)
        flagged_ids = {f["held_out_id"] for f in flags}
        self.assertNotIn(
            "recursion-week-01-v11",
            flagged_ids,
            "recursion-week-01-v11 (meet) was unexpectedly flagged by similarity guard.",
        )

    def test_copy_detection_learner_visible_item_fails_guard(self):
        """Copy detection: putting a learner-visible item body into a held-out item

        under a new family_id must be flagged by the guard.
        """
        pack_copy = copy.deepcopy(self.current_pack)

        # Find a learner-visible item (e.g. repeat_mark or double)
        source_item = next(
            it for it in pack_copy["items"]
            if not it.get("held_out") and it.get("id") == "recursion-application-v9"
        )

        synthetic_heldout = {
            "id": "synthetic-heldout-copied-item-01",
            "family_id": "synthetic-new-family-xyz",
            "body": source_item["body"],
            "held_out": True,
        }
        pack_copy["items"].append(synthetic_heldout)

        flags = find_heldout_similarity_flags(pack_copy)
        flagged_ids = {f["held_out_id"]: f for f in flags}

        self.assertIn("synthetic-heldout-copied-item-01", flagged_ids)
        matched_ids = {s["id"] for s in flagged_ids["synthetic-heldout-copied-item-01"]["matched_sources"]}
        self.assertIn("recursion-application-v9", matched_ids)

    def test_copy_detection_lesson_code_block_fails_guard(self):
        """Copy detection: putting a lesson code block into a held-out item

        under a new family_id must be flagged by the guard.
        """
        pack_copy = copy.deepcopy(self.current_pack)

        # Lesson 3 fence 0: countdown
        synthetic_heldout = {
            "id": "synthetic-heldout-copied-lesson-01",
            "family_id": "synthetic-new-family-lesson-abc",
            "body": "def countdown_copy(n):\n    if n == 0:\n        return 'go'\n    return str(n) + ', ' + countdown_copy(n - 1)\n",
            "held_out": True,
        }
        pack_copy["items"].append(synthetic_heldout)

        flags = find_heldout_similarity_flags(pack_copy)
        flagged_ids = {f["held_out_id"]: f for f in flags}

        self.assertIn("synthetic-heldout-copied-lesson-01", flagged_ids)
        matched_ids = {s["id"] for s in flagged_ids["synthetic-heldout-copied-lesson-01"]["matched_sources"]}
        self.assertIn("lesson-recursion-as-self-call-v9_fence_0", matched_ids)


if __name__ == "__main__":
    unittest.main()

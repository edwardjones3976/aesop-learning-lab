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


# Documented allowlist of (held-out item, matched source) pairs whose shape matches.
# Keying by pair means an allowlisted item still fails on any NEW match.
# Each entry MUST have a written reason; a pair that stops matching fails CI (stale).
CURRENT_PACK_ALLOWLIST = {
    ("recursion-halving-transfer-01-v9", "base-case-trace-01-v9"): (
        "Day-1 near-transfer, not a primary outcome. leaf_count doubles a decremented call "
        "like the studied f(n); Codex's step-7 review rejected it as an unfamiliar-transfer claim."
    ),
    ("recursion-halving-transfer-01-v9", "recursive-case-application-02-v9"): (
        "Same day-1 near-transfer item; the savings practice also multiplies a decremented call."
    ),
    ("scope-week-01-v9", "scope-keyword-transfer-01-v9"): (
        "OWNER DECISION 2026-10-21: keep as is. The day-7 primary check and the day-1 check (answered first) are "
        "both two-parameter functions appending a string default. The day-7 item's tested idea, "
        "rebinding a parameter locally while the caller's variable is unchanged, is absent from "
        "the day-1 item, and Codex's step-7 review accepted it. The owner decided to keep it "
        "rather than replace it in a new content version."
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
        pairs = {(f["held_out_id"], s["id"]) for f in flags for s in f["matched_sources"]}

        for pair, reason in CURRENT_PACK_ALLOWLIST.items():
            self.assertTrue(reason.strip(), f"Allowlist entry {pair} has no written reason.")
            self.assertIn(pair, pairs, f"Stale allowlist entry: {pair} no longer matches.")

        self.assertEqual(sorted(pairs - CURRENT_PACK_ALLOWLIST.keys()), [],
                         "Unallowed similarity flags in the current pack.")

    def test_earlier_held_out_check_counts_as_exposure(self):
        """A day-7 check copied from a day-1 check (answered first) is flagged."""
        pack_copy = copy.deepcopy(self.current_pack)
        day1 = next(it for it in pack_copy["items"]
                    if it.get("held_out") and it.get("check_delay_days") == 1)
        pack_copy["items"].append({"id": "synthetic-day7-copy", "family_id": "synthetic-new-family",
                                   "body": day1["body"], "held_out": True, "check_delay_days": 7})
        flags = {f["held_out_id"]: f for f in find_heldout_similarity_flags(pack_copy)}
        self.assertIn(day1["id"], {s["id"] for s in flags["synthetic-day7-copy"]["matched_sources"]})
        # The reverse direction is not exposure: the day-1 check comes first.
        self.assertNotIn("synthetic-day7-copy",
                         {s["id"] for s in flags.get(day1["id"], {"matched_sources": []})["matched_sources"]})
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

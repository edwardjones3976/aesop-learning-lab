# Aesop mission continuation: content correction candidate

At continuation, `codex/foreman-v1` was clean at `1af6171fd12ef360e2680e0edaa83727d98927db`. Draft PR #20 was open with no reviews or reported CI statuses. Director-Orchestrator remained clean and read-only. Researchers MCP remained unavailable for searches; Claude and Cursor contacts remained advisory-only, without production-review authority. No paid provider call is reserved.

## Selected objective

Create a **new draft content version** correcting the four findings in `docs/independent-content-review.md`, while retaining the exact older pack for learners with existing records. Do not promote candidate keys or reuse the old review receipts as approval of changed content. The new version must validate, its quoted string answers must score consistently with hints, its recursive example must terminate on its stated input domain, and a database restart must not silently show a different pack to an existing learner.

The competing next steps were (1) this correction, (2) a one-week check, and (3) the fixed experiment. Under the mission weights (learning objective 30%, deliverability 25%, measurement 20%, leverage 15%, progress per dollar 10%), the correction scores 4.6/5, the one-week check 3.8/5, and the experiment 3.5/5. These ordinal estimates reflect prerequisites: the latter two would use the known ambiguous candidate content. The correction is feasible without a paid model call, but full release remains blocked by independent review.

**Owned files:** a new versioned JSON pack, preview pack selection and display, focused content and persistence tests, and documentation. **Acceptance:** old pack byte-for-byte unchanged; new pack parses with no validation issues; all four findings are demonstrably corrected; old v1 learner data remains available without reinterpretation; new learners receive v2; export/delete work; full relevant tests pass. **Budget:** $0 reserved for external paid calls; host token and tool costs remain unavailable. **Review:** Codex authored changes require a distinct eligible non-author review before promotion or merge. No changes to the fixed experiment protocol or protected branches.

## Implementation and limits

`pack-m1-draft.2.json` is a separate complete snapshot. All five concept content versions advance to `v2`, so no existing `v1` lesson or item is silently rewritten. The two string trace keys accept unquoted text and both Python quote styles. The recursion recognition choice has a stopping case, and its lesson now states a positive-integer input domain and the failure of this exact function to terminate for zero or negative input. All keys remain `candidate`, and v2 has no review receipts. The original pack and review report remain historical evidence.

The preview selects v1 when learner events reference v1, otherwise v2. An impossible mixed-version learner history fails closed instead of merging evidence from different content. Deleting learner data explicitly moves the running preview to v2; content rows remain in SQLite for referential integrity, while attempts, lessons, drafts, hints, reviews, and revisions are deleted. Historical v1 content stays available for an active v1 learner but retains its flagged draft limitations. A reviewer must check v2 before it can be released.

## Verification and current local addresses

`PYTHONPATH=src; py -m unittest discover -s tests -q` passed 107 tests after the versioned correction. `npm test` in `web` passed 16. The new pack parses without validator issues; tests execute the trusted authored trace snippets against candidate keys, check both quote styles, and verify the stopping case and domain statement. Persistence tests confirm a v1 lesson remains on v1 across restart, v2 persists across restart, mixed-version history is rejected, and explicit deletion moves the running preview to v2. Headless Edge rendered the v2 recommendation and evidence at desktop and mobile widths without page errors or horizontal overflow.
An isolated HTTP smoke on port 8777 posted a lesson completion with the matching Origin and read it back from v2, verifying that the configurable local port works for writes.

The existing local database had seven v1 attempts at the time of this check, so `http://127.0.0.1:8775/` remains on `m1-draft.1` with those records intact. A separate empty database serves `m1-draft.2` at `http://127.0.0.1:8776/`. The v2 test session did not transfer or delete v1 records. No human learning-effect claim or independent review approval follows from these checks.

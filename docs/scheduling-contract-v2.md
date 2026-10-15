# One-day and one-week check contract

This extends [the original scheduler contract](scheduling-contract-v1.md) for the
`m1-draft.3` development pack. The original v1 and v2 packs and learner records
remain pinned to their versions. The new pack uses `pilot-v2` in recommendations.

Each activity has `check_delay_days`: zero for practice, one or seven for a
held-out check. The delay is measured from the persisted lesson completion time.
The earlier check must have an attempt before the seven-day check becomes
eligible. Its score and hint level do not determine eligibility, so a weak
day-one result does not remove the opportunity to observe week-one retention.
The seven-day item has a different, previously unattempted family. An attempted
held-out item is not offered again.

An unassisted correct scored answer after lesson completion is still needed to
open the first check. Practice remains available before and after either due
time. A learner can choose practice when a check is due. `nextCheckAt` is the
next eligible check time, which may already be past. It is not a claim that an
attempt occurred or that a learner retained the concept.

`delayedChecks` records each attempted interval with `checkDelayDays`, assistance,
score, and `independentSuccess`. `delayedOutcomeByDay` reports `observed` or
`insufficient_evidence` for each interval separately. Both keys and instructional
items remain unreviewed candidates; these observations are not mastery estimates.

# Micro-unit engine (A2)

`aesop_lab.micro.engine.MicroUnitEngine(pack, store, now, daily_limit=3)`
uses a validated `MicroUnitPack`, a `SQLiteStore`, and a callable clock returning
an aware datetime. This is an engine/storage API; existing Python content,
Preview, protocols and UI continue on their existing paths.

## API

- `next_activity()` returns a dictionary (`kind="check"` or `kind="unit"`),
  or `None`. Checks include the prompt and check ID, without the key. A new
  unit suggestion includes its ID; call `start_unit` to receive its lesson.
  A suggestion does not reserve or expose content. Unfinished units can resume.
- `choose_method(unit)` returns a method ID. Existing assignments are stable.
  Before assignment, this is a deterministic proposal given the current history;
  feedback or assignments arriving before `start_unit` can change the proposal.
- `start_unit(unit)` persists assignment and exposure and returns only the
  assigned variant in `lesson`, plus the method and unit IDs. Repeated calls
  preserve the method and original timestamps. New assignments count toward the
  daily cap; existing units can resume after that cap. The assignment transaction
  serializes competing connections, including warm-up and cap decisions.
- `complete_unit(unit)` records completion once. The unit must have started.
- `answer_check(unit, answer, assisted=False)` scores using the existing
  whitespace-normalizing, case/punctuation-preserving `normalize_answer`, against
  the candidate accepted strings. It returns the persisted first response,
  score and classification. Repeats cannot replace the first response, including
  an early, assisted or incorrect response. Completion is required; direct early
  or late submissions are retained for reporting.
- `outcomes_by_method()` returns all methods mapped to `(matched_key, 1.0)`
  observations under `outcomes`, and unit IDs under `excluded` for `early`,
  `late`, `assisted`, and `missing`. Missing means a completed unit without a
  response, including checks still pending. Uncompleted units add no evidence.
  Assisted takes precedence over timing in these mutually exclusive buckets.
- `ranking()` returns ordered `methods` with `method`, `posterior_mean`,
  `probability_best`, `effective_checks`, `alpha`, `beta`; plus `confidence`,
  `show_ranking`, and exclusions. It delegates to #60's `rank_methods` unchanged.

Dictionary outputs and each ranking method carry
`provisional="provisional (draft keys)"`. Draft keys never block estimating or
returning an ordering. `show_ranking` retains #60's evidence availability rule.
Method IDs returned by `choose_method` are identifiers, not learner wording.
Units can be passed as IDs or pack unit objects; the canonical pack object is used.

## Schedule and eligibility

Unanswered checks are offered first, oldest completion first, once elapsed time
since completion reaches seven full days. Overdue checks remain answerable and
are classified late. Checks never consume the new-unit allowance. Then unfinished
units resume, then the first unseen pack unit is suggested if the daily allowance
permits it. Assignment dates use calendar days in the timezone supplied by `now`;
step C must consistently supply the learner's chosen timezone. The default cap
is three new units per calendar day per pack.

The descriptive protocol's exact inclusive window applies: before seven elapsed
days is early; exactly seven through exactly fourteen days is in-window; after
fourteen days is late. Only received, first, unassisted, in-window responses feed
assignment posteriors and ranking, once per exposure at weight one. No imputation
for missing checks, practice scoring, or repeated-check evidence is added.

## Storage and #60 mapping

Schema **v17** adds `micro_exposures` and `micro_check_attempts`. Both use
`(pack_id, unit_id)` as primary key: one exposure and one decisive check per unit
in a learner's local database. Exposure rows hold method and assignment, exposure
and completion timestamps. Check rows hold check ID, first answer, correct/incorrect
score status, timestamp, and assisted flag; a composite foreign key references
the exposure. Every new storage write calls `require_active_learner`.
`export_all` includes `microExposures` and `microCheckAttempts`; `delete_all`
removes checks before exposures, retaining the existing secure deletion behavior.
The additive v16 migration does not rewrite existing tables or learner history.
The real compressed v16 fixture and its provenance are in `tests/fixtures/micro-v16.md`.

Assignment uses a SHA-256 seed from learner ID, pack ID and unit ID, with a local
RNG and sorted method IDs. Warm-up picks among methods with the fewest assignments
until each has two, including pending checks. Thereafter a 20% uniform draw and
80% independent Beta Thompson draw use only received eligible outcomes. Priors
are Beta(1,1), success/failure increments are one. This implements #60's policy
and independent-unit rule without changing its estimator or confidence thresholds.
A learner ID is created only behind consent. Ranking Monte Carlo is separately
seeded from learner/pack and the string `ranking`.

## Validation and deliberate breaks

`tests/test_micro_unit_engine.py` uses a controlled aware clock and the sample
pack, expanded into distinct synthetic units where needed. The 60-day seeded
learner studies three units daily (180 exposures) and receives 159 day-7 checks.
Recall probabilities are 0.9, 0.5 and 0.2 in sorted method order; outcome RNG seed
is 20261021, identity is `synthetic-42`. The true best (`cued_retrieval`) ranks first.
Posterior means are 0.9262, 0.5556 and 0.3125, with 120, 25 and 14 eligible
checks respectively. The confidence label is `likely`; `show_ranking` is true.
This single synthetic history verifies integration, not human effectiveness or
ensemble calibration. Real content needs many more independently authored units
than the four-unit sample provides.

Run `PYTHONPATH=src python scripts/micro_unit_engine_break_checks.py` to repeat
one deliberate mutation per key test, in memory. Each must cause an assertion
failure, not merely a runtime/import error. Mutations remove the cap, offer checks
a day early, overwrite exposure timestamps, replace first responses, remove
warm-up, change the exploration boundary to 80%, admit excluded outcomes, remove
consent checks, retain check rows on deletion, leave migration version at 16,
and reverse scores in the synthetic learner. All **11/11** breaks produced
assertion failures in their corresponding tests. The source was unchanged by
these runs.

Final validation on this worktree:

- `PYTHONPATH=src python -m unittest discover -s tests -q`: **335 passed**
  (including 11 engine tests).
- `node --test tests/foreman_web_contract.test.mjs tests/personal_comparison_web.test.mjs`:
  **51 passed**.
- Deliberate breaks: **11/11 detected**; focused compile checks and
  `git diff --check` passed.

The first full run exposed migration tests that reset `user_version` on an
already current schema. Making the additive table creation idempotent preserved
those legacy tests; the final full run above passed. The genuine v16 fixture
separately verifies the actual upgrade and preservation of every original row.

## Step C decisions

HTTP routes and payload contracts, UI integration, learner timezone selection,
pack enrollment/switching, explicit assistance capture, and wording for pending,
missed, late and close results remain for step C. The engine supplies exclusion
IDs and model confidence; the UI must explain draft-key uncertainty and must not
imply the leader's confidence certifies the entire ordering. Pack IDs must be
stable and packs immutable during a run; versioning or replacing enrolled content
needs a separate policy. No push, PR, approval or merge is part of A2.

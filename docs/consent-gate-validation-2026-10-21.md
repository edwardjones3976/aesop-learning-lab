# Consent gate: round 2, step 8

Local implementation on `feat/consent-gate`, based on
`f5b700e3481eefd0b86f5d22804e50d920e8c0cb`. No push, PR, approval or merge.
Claude integrates; Cursor reviews/merges under the existing gates.

Schema v16 adds `learner_consent(slot, text_version, confirmed_at)`. Confirmation
is idempotent and records `consent-v1` before any enrollment. Export includes
raw records as `learnerConsent`. Deletion removes consent atomically with learner
data; the existing tombstone prevents re-enrollment until Start again. Restart
only clears that tombstone, so new consent is then required.

Legacy choice: **migration**, rather than lazy recording. Existing identities
receive `legacy-pre-gate` and the migration's UTC timestamp; this timestamp is
not represented as an earlier affirmative consent. Existing runs continue.
The gzip fixture was generated using the unchanged v15 base code, with a lesson
opening, before editing storage. Its test compares every preexisting table row.

The consent screen replaces the workspace and navigation until confirmed, has
one button (I agree — start learning), and no inputs. Its shipped text is:

> Your answers, hint use, confidence, outside-study notes and timing are stored on this computer only. They are not sent to any outside service, including AI models.
>
> Results are compared with draft answer keys. They stay provisional and are not a grade or a judgment of what you know.
>
> One person's answers are not enough evidence to show which teaching method works better.
>
> You can stop at any time, and you can ask for your data to be deleted.

The phrase about a judgment of what you know expresses the requested limit
without putting the word `mastery` into consent markup.

Enforcement uses `SQLiteStore.require_active_learner`, preserving the prior
`learner_deleted` priority and adding HTTP 409 `consent_required`. Preview and
learning-service entry points enforce it, with an additional HTTP route guard.
The v2 response retains `error` and also exposes `code`.

Gated v2 endpoints:

- GET `/api/v2/session`, `/api/v2/personal-comparison`.
- POST `/api/v2/lesson`, `/api/v2/lesson-completions`, `/api/v2/first-answers`,
  `/api/v2/hints`, `/api/v2/attempts`, `/api/v2/self-reviews`,
  `/api/v2/revisions`, `/api/v2/overrides`.
- POST `/api/v2/personal-comparison/{enroll,start,complete,open,hint,answer,reveal,override}`.

GET overview and export stay read-only and available before consent. Overview
includes `consentRequired`; export creates no identity. POST consent records
only consent. Delete and restart remain available and create no learner rows.

The v1 API can write learner state, so the gate also covers GET
`/api/v1/session/next` and POST `/api/v1/attempts`, `/api/v1/self-reviews`,
`/api/v1/answer-revisions`, plus the underlying lesson-completion service.
Export and deletion remain available. No v1 consent route was added; confirmation
is through the preview or storage, with v1 changes limited to enforcement.
No protocol modules, packs, or classifications changed. Runbook step 1 retains
the owner's conversation, describes the app record and removes the workaround.
Step 3 and 4 command blocks compare byte-for-byte equal to the base content.

Validation commands (PowerShell: set `$env:PYTHONPATH` to the absolute `src`
path so browser subprocesses inherit it):

```text
PYTHONPATH=src python -m unittest discover -s tests -q
node --test tests/foreman_web_contract.test.mjs tests/personal_comparison_web.test.mjs
(cd web && npm test)
(cd tests/browser && npx playwright test)
PYTHONPATH=src python scripts/check_consent_breaks.py
```

Final validation:

| Suite | Passed | Failed |
|---|---:|---:|
| Python unittest discovery | 280 | 0 |
| Foreman and personal-comparison Node contracts | 51 | 0 |
| web npm test | 17 | 0 |
| Playwright Chromium | 6 | 0 |

`python -m compileall -q src tests scripts/check_consent_breaks.py` and
`git diff --check` also passed. The six new Python tests passed again after
mutations were restored. Node and Playwright were rerun after correcting UTF-8
encoding in the new consent button label.

All **14 deliberate breaks failed as intended**, with no survivors. The
repeatable runner restores exact original source bytes in `finally` blocks.
Run it separately from normal suites.

| Deliberate break | Detected by |
|---|---|
| Bypass v2 active/consent check | fresh endpoints: 19 assertions failed |
| Bypass v1 active/consent check | v1 endpoints: 4 assertions failed |
| Confirmation does not persist | consent/enrollment test failed |
| Treat legacy learner as unconsented | legacy opens/works test failed |
| Delete exposure rows during migration | v15 preservation test failed |
| Keep consent after deletion | deletion/restart test failed |
| Auto-consent on restart | deletion/restart test failed |
| Remove privacy statement | Node consent markup test failed |
| Add mastery wording | Node consent markup test failed |
| Add prechecked checkbox | Node consent markup test failed |
| Render workspace before consent | Node workspace contract failed |
| Ignore consent in boot | Node boot contract failed |
| Bypass browser boot gate | fresh-server Playwright test failed |
| Bypass server gate | fresh-server Playwright test failed |

Initial setup issues were resolved: browser dependencies needed `npm ci`;
Python subprocesses needed an absolute `PYTHONPATH`; historical journeys needed
explicit consent; downgrade-style old migration tests required idempotent table
creation, consistent with the older migrations. No suite failure remains.

Changed implementation: `src/aesop_lab/storage/sqlite.py`, `src/aesop_lab/foreman.py`,
`src/aesop_lab/api/{http,service}.py`, `foreman_web/{app.js,index.html,style.css}`.
Tests: new `tests/test_consent_gate.py`, v15 fixture and provenance,
`scripts/check_consent_breaks.py`, consent contracts and browser journey, and
explicit confirmation in the preexisting API, Foreman, registry, key lock,
M1 journey, personal comparison, pilot journey and synthetic-cohort tests.
Docs: this report and `docs/real-learner-runbook.md`.

Scope/uncertainties: no known implementation blocker. The privacy text reflects
the existing local-only architecture; this task is not a comprehensive network
privacy audit or a real-learner pilot. Non-author review and repository gates
remain for integration. Browser validation uses Chromium, as configured in CI.

Exact changed files:

- `docs/consent-gate-validation-2026-10-21.md`
- `docs/real-learner-runbook.md`
- `foreman_web/app.js`
- `foreman_web/index.html`
- `foreman_web/style.css`
- `scripts/check_consent_breaks.py`
- `src/aesop_lab/api/http.py`
- `src/aesop_lab/api/service.py`
- `src/aesop_lab/foreman.py`
- `src/aesop_lab/storage/sqlite.py`
- `tests/browser/foreman_smoke.spec.mjs`
- `tests/fixtures/consent-v15.md`
- `tests/fixtures/consent-v15.sqlite3.gz`
- `tests/foreman_web_contract.test.mjs`
- `tests/test_api.py`
- `tests/test_consent_gate.py`
- `tests/test_foreman.py`
- `tests/test_foreman_http.py`
- `tests/test_foreman_registry.py`
- `tests/test_key_outcome_locks.py`
- `tests/test_m1_journey.py`
- `tests/test_personal_comparison.py`
- `tests/test_personal_pilot_journey.py`
- `tests/test_synthetic_cohort_v8.py`

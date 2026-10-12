# Local API development fixture

The local HTTP service currently accepts only the explicit development fixture.
Its answer keys have no human review receipts. Every response carries
`developmentOnly: true`; the service rejects a claim that this catalog is
reviewed. Do not release it as learning content.

Run from a checkout with `PYTHONPATH=src`:

```powershell
$env:PYTHONPATH = 'src'
py -m aesop_lab.api --development-fixtures --db .local/aesop-dev.sqlite3
```

The server binds to `127.0.0.1:8766`. The fixture's lesson completion is
recorded on first start and remains fixed in SQLite across restarts. GET
`/api/v1/session/next?availableMinutes=20&mode=recommended` is read-only;
use `mode=practice` to choose routine practice while a delayed check is due.
POST `/api/v1/attempts` uses the body in `api-v1.md` and records the first
answer and highest hint level before the next scheduling decision.

Only these two endpoints are implemented in this slice. Reviewed pack loading,
the browser HTTP adapter, and open-ended review endpoints are integration work.
The current service accepts a real lesson completion through
`LearningService.complete_lesson()`; the CLI calls it for the fixture only.

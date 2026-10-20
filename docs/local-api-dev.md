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

The server binds to `127.0.0.1:8766` and accepts requests addressed to
`127.0.0.1:8766` or `localhost:8766`. Browser requests from the local UI at
`http://127.0.0.1:8765` or `http://localhost:8765` are allowed; other
`Origin` values are rejected. POST and DELETE requests without one of those
allowed `Origin` headers return 403 `forbidden_request`; GET and OPTIONS are
unchanged and still accept requests without `Origin`. POST endpoints require
`Content-Type: application/json`; DELETE needs no JSON content type. Loopback
binding alone does not validate browser requests.
The fixture's lesson completion is
recorded on first start and remains fixed in SQLite across restarts. GET
`/api/v1/session/next?availableMinutes=20&mode=recommended` is read-only;
use `mode=practice` to choose routine practice while a delayed check is due.
POST `/api/v1/attempts` uses the body in `api-v1.md` and records the first
answer and highest hint level before the next scheduling decision. It also
accepts optional `availableMinutes` (default 20); send the session's value
when submitting a delayed check so the same time-budget gate applies.

The browser at `http://127.0.0.1:8765/` now uses this local API by default.
Run `py -m http.server --bind 127.0.0.1 8765` from `web/` in another terminal. Add
`?scenario=default` to use the isolated in-memory fixture instead.

The service also provides `POST /api/v1/self-reviews`,
`POST /api/v1/answer-revisions`, `GET /api/v1/export`, and
`DELETE /api/v1/data`. The development catalog includes an open-ended
review item. Deleting learner data leaves the content catalog intact; restart
the development server to start a new fixture lesson clock.

Reviewed pack loading and five-concept progression remain integration work.
The current service accepts a real lesson completion through
`LearningService.complete_lesson()`; the CLI calls it for the fixture only.

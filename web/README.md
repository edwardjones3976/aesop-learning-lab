# Web session

Thin practice UI for package U1. The page talks only to an injected `LearningApi`. `src/main.js` uses the local HTTP adapter by default; `?scenario=default` selects the fixture adapter.

Open-ended activities demonstrate guided self review: lock the first answer, compare it against every rubric criterion with quoted evidence, save the review, then reveal an annotated example and optionally save a separate revision. The local API stores attempts, reviews, and revisions in SQLite. The fixture keeps records in memory for isolated tests.

Open this directory through a local server so the modules load:

```text
python -m http.server 8765
```

Start the local API as described in `../docs/local-api-dev.md`, then visit
`http://127.0.0.1:8765/`. The fixture works without the API at
`http://127.0.0.1:8765/?scenario=default`.

Query scenarios: `?scenario=empty`, `?scenario=storage`, and `?scenario=unavailable`.

Tests:

```text
npm test
```

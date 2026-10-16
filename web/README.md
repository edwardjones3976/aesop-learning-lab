# Web session

Thin practice UI for package U1. The page talks only to an injected `LearningApi`. `src/main.js` injects the fixture adapter.

Open-ended fixture activities now demonstrate guided self review: lock the first answer, compare it against every rubric criterion with quoted evidence, save the review, then reveal an annotated example and optionally save a separate revision. The fixture keeps records in memory for the current page session. The Python SQLite adapter stores review and revision events durably; a local HTTP API connecting the browser to it is still pending.

Open this directory through a local server so the modules load:

```text
python -m http.server 8765
```

Then visit `http://127.0.0.1:8765/`.

Query scenarios: `?scenario=empty`, `?scenario=storage`, and `?scenario=unavailable`.

Tests:

```text
npm test
```

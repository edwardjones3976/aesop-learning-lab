# Web session

Thin practice UI for package U1. The page talks only to an injected `LearningApi`. `src/main.js` injects the fixture adapter.

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

# Browser API v1 contract

The browser client uses an injected `LearningApi` adapter. A local HTTP implementation may be added behind it; the UI must also run against a fixture adapter for isolated testing. JSON field names below are stable for V1. Timestamps are UTC ISO 8601 strings.

## `GET /api/v1/session/next?availableMinutes=20`

```json
{
  "activity": {
    "id": "functions-base-case-01",
    "conceptId": "base-case",
    "contentVersion": "v1",
    "familyId": "base-case-trace-a",
    "type": "trace",
    "evidenceKind": "application",
    "prompt": "What value does this function return for n = 2?",
    "body": "def f(n):\n    if n == 0: return 1\n    return n * f(n - 1)",
    "choices": [],
    "hints": [
      {"level": "nudge", "text": "Find the stopping condition."},
      {"level": "targeted", "text": "Evaluate f(0), then f(1)."},
      {"level": "worked_solution", "text": "f(0)=1, f(1)=1, f(2)=2."}
    ]
  },
  "recommendation": {
    "policyVersion": "pilot-v1",
    "reason": "This concept is due for an independent check.",
    "evidenceAttemptIds": []
  }
}
```

The response can instead contain `"activity": null` with a clear `reason` when nothing is due. The client does not infer or invent a recommendation.

## `POST /api/v1/attempts`

```json
{
  "activityId": "functions-base-case-01",
  "contentVersion": "v1",
  "firstAnswer": "2",
  "hintLevel": "none",
  "confidence": 0.7,
  "outsideStudy": "none",
  "outsideStudyDetail": null,
  "activeSeconds": 54
}
```

Response:

```json
{
  "attemptId": "example-attempt-1",
  "scoreStatus": "correct",
  "gradingMethod": "reviewed_exact_key",
  "assisted": false,
  "nextReason": "Try a different application tomorrow."
}
```

The server records the first answer before hints or solution reveal. The client sends the highest viewed hint level. `confidence` and `outsideStudy` may be null outside an experiment. In an experiment, the UI prompts for them and the server records missing answers explicitly.

## Learner controls

- `GET /api/v1/insights` returns separate evidence by kind, due reviews, recommendation reasons, and experiment findings with scope and uncertainty.
- `POST /api/v1/recommendations/override` records the learner choice and reason without rewriting the original recommendation.
- `GET /api/v1/export` returns the local record as JSON.
- `DELETE /api/v1/data` deletes all learner records after a confirmation step; it does not delete the reviewed content pack.

Errors use `{ "code": "stable_code", "message": "human-readable explanation" }`. Validation failures return HTTP 400; absent IDs return 404; unavailable local storage returns 503. The UI displays these messages without treating the attempted action as successful.

# Continued practice and delayed-check contract

The scheduler is a pure function in `aesop_lab.scheduler`. Storage supplies the
current concept, content version, lesson completion time, reviewed activities,
attempts, and encountered item families. The API owns that mapping; the browser
does not choose activities or decide whether evidence counts.

`GET /api/v1/session/next` accepts `availableMinutes` and an optional
`mode=recommended|practice` query parameter. `recommended` is the default.
The response retains the `activity` and `recommendation` fields in
`api-v1.md` and adds:

```json
{
  "mode": "practice",
  "nextCheckAt": "2026-01-02T12:00:00Z",
  "activity": { "id": "reviewed-practice-item" },
  "recommendation": {
    "policyVersion": "pilot-v1",
    "reason": "Continue practice by choice; an independent check remains available.",
    "evidenceAttemptIds": []
  }
}
```

`nextCheckAt` is nullable. Before the 24-hour interval, it is the earliest
possible check time, provided the learner also has qualifying evidence and an
unused held-out item. When a check is due, it remains present if the learner
chooses practice. It is not a lockout or a promise that a check will be
available. The UI can show a clock and the server's reason, but must not turn
the time into a disabled practice state. When no activity is available,
`activity` and `recommendation` are null and the response includes a `reason`.

A qualifying attempt is correct and unassisted on the current content version.
The check is an unused, held-out application or transfer item from a family the
learner has not encountered. Its 24-hour delay is measured from lesson
completion. An answer made with hints or a self-review of an ungraded answer
does not satisfy the qualifying-attempt rule. A held-out item is never routine
practice, and an attempted held-out item is never selected again. The learner
can request more practice at any time; this does not consume the check.

The API must admit only reviewed content into `LearnerState`. It persists each
first answer and assistance level before scheduling another item, so a refresh
cannot reset the queue or fabricate independent evidence. Until the content
pack has human review receipts, the API can be exercised with development
fixtures but must not present them as released learning content.

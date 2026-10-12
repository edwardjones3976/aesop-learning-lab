# Delivery board

Three provider lanes have equal initial budgets of 12 planning points. Points are a sizing tool; rebalance when evidence shows a different cost. Each provider owns three four-point packages. Cross-review is reciprocal and no provider approves its own work.

| ID | Provider | Package (4 points each) | Done when |
|---|---|---|---|
| C1 | Codex | Domain types, repository ports, contract fixtures | Records and invariants documented; fixtures validate |
| C2 | Codex | SQLite adapter, migrations, export/delete | Round-trip and migration checks pass |
| C3 | Codex | Learner-state rules, scheduler, application API | Reasoned recommendation and delayed-review slice pass |
| L1 | Claude | Reviewed programming concept pack and validation schema | ~20 linked concepts with versioned content and source review receipts |
| L2 | Claude | Assessment and hint ladder | Unassisted/assisted scoring and honest ungraded path pass |
| L3 | Claude | Experiment manager and outcome reporting | Seeded fixed comparison, exposure log, uncertainty report pass |
| U1 | Cursor | Session and practice UI | Keyboard-usable lesson, attempt, hint, and pause flow works |
| U2 | Cursor | Insights and learner controls | Evidence, override, correction, export, and delete flows work |
| U3 | Cursor | Content authoring preview and accessibility pass | Preview validates versions; accessibility checklist passes |

## Milestones

- M0: Brief, contracts, ownership, initial repo and CI. Exit: all three providers accept package boundaries and contract fixtures.
- M1: Core vertical slice with five concepts. Exit: local end-to-end practice and delayed check, no runtime AI.
- M2: Twenty-concept pack and fixed comparison. Exit: all V1 acceptance tests and content review pass.
- M3: Pilot and evidence review. Exit: usability, data-control, and experiment-quality issues triaged; claims remain appropriately limited.

## Integration and mending procedure

1. Each package uses its own branch/worktree and touches only its owned module, tests, and necessary contract proposal. Name PRs by package ID.
2. The integrator (Codex) checks the declared contract, runs targeted tests, and builds the vertical slice on an integration branch. A different provider reviews each package: Cursor reviews Codex, Codex reviews Claude, Claude reviews Cursor.
3. A failing merge is logged with the smallest reproducer, owner, broken contract or data fixture, severity, and rollback path. The owner repairs its module; interface disagreements go to a short recorded contract decision before edits.
4. Rebase or merge the repair into the integration branch, run the failed check and affected contract tests, then rerun the full release gate on the exact candidate. Do not silently rewrite experiment data or change a live comparison protocol to mend a failure.
5. Release only after the integrated candidate passes the local acceptance journey and independent review. Unresolved defects stay visible in the board and block the relevant milestone.

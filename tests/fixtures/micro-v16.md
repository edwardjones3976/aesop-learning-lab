# v16 migration fixture

`micro-v16.sqlite3.gz` is a real SQLite database produced by the unmodified
v16 `SQLiteStore` from worktree base `d36a8e1` (read with `git show HEAD:...`
before this task's commit). It was opened on the existing synthetic
`consent-v15.sqlite3.gz` fixture, allowing the actual v16 migration to add
legacy consent. It retains the cached content, learner identity, assignment,
and exposure from that fixture. No schema version was manually rewritten.
Gzip uses mtime zero. `test_v16_migration` verifies version 16 before opening,
then compares every row of every original table after migrating to v17.

# v15 migration fixture

`consent-v15.sqlite3.gz` was generated with the unmodified v15 code at the
worktree base commit `f5b700e3481eefd0b86f5d22804e50d920e8c0cb`, before implementing this gate:

```python
preview = Preview(Path("consent-v15.sqlite3"))
preview.lesson(preview.pack.learning_order()[0])
preview.store.close()
```

The database contains the cached current pack plus one generated identity,
assignment and exposure (synthetic data only). It was gzip compressed without
rewriting the schema. The migration test compares every original table row.

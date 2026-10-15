# Foreman local preview

This branch is a separate development preview of the draft Python functions and recursion pack. It does not modify `master` or the existing web app.

Start it from the repository root:

```powershell
py scripts/run_foreman.py
```

Open <http://127.0.0.1:8775/>. The server binds only to the loopback interface and keeps learner data in `.local/foreman.sqlite3` within this worktree. It has no cloud account or public address.

The pack remains `draft`, with candidate answer keys and no independent review receipts. Automatic matches are development feedback only. The interface records a lesson completion when the learner presses the lesson button, saves each first answer before opening hints, persists each hint view, and links an idempotent attempt to the saved answer. Export and deletion include saved answers and hint views. A held out check uses the existing scheduling policy; it is not presented as a mastery decision.

Run checks with:

```powershell
$env:PYTHONPATH='src'
py -m unittest discover -s tests -q
cd web
npm test
```

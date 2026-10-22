"""One AI learner (Antigravity) through the frozen order-v1 contrast, plus a zero-shot pretest.

SIMULATION ONLY. The learner is one language model: a witness, reported on its own.
It is not evidence about people, and synthetic learners supply the gate rates
(scripts/simulate_contrast_gate.py). Caption: "one model".

Rules from aesop-declutter-plan/simcourse-decision.html section 3:
- Every lesson step and every check is its own fresh, stateless bridge call from an
  empty folder, so a lesson never sits next to its check.
- A lesson is split at its question line so the order really differs: predict_first
  asks before explaining; worked_then_retrieve explains, then asks. Both arms get two
  calls of the same shape. The learner's own answer is shown back in the second call.
- Memory between days is a capped notebook of the learner's own one-line notes
  (NOTEBOOK_CAP most recent). Each check call replays it shuffled, with each note
  omitted with probability OMIT. Held-out check prompts, keys and correctness never go in.
- Pretest: before any lesson, every invented word is asked zero-shot. Pretest calls
  batch PRETEST_BATCH words, since no lesson exists to cue; each item is logged.

Simulated UTC clock: lessons at 12:00 (3 a day for days 0-21), due checks at 18:00, and
the day-28 status at day zero + 28 days + 1 hour. Write everything to --run-dir,
outside the repository.

    py scripts/ai_learner_contrast_run.py --run-dir C:\\path\\to\\run
    py scripts/ai_learner_contrast_run.py --run-dir DIR --pretest-only
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import html
import json
from pathlib import Path
import random
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aesop_lab.content.micro_unit import load_micro_unit_pack  # noqa: E402
from aesop_lab.contrast.protocol import ORDER_V1  # noqa: E402
from aesop_lab.micro.engine import MicroUnitEngine  # noqa: E402
from aesop_lab.storage.sqlite import SQLiteStore  # noqa: E402

BRIDGE = Path.home() / ".claude/skills/agent-bridge/ask.ps1"
PACK = ROOT / "content/drafts/order-v1-invented-pack.json"
START = datetime(2026, 11, 2, tzinfo=timezone.utc)
STUDY_DAYS, UNITS_PER_DAY = 22, 3
NOTEBOOK_CAP, OMIT, PRETEST_BATCH = 30, 0.3, 25
SEED = 20261021

BRIEF = ("You are role-playing a learner in a vocabulary app that teaches invented words. "
         "The words are made up, so you cannot know them in advance. Answer honestly from what "
         "you are shown here, without using any tools, files or searches. Reply in plain text only.\n\n")


class LearnerUnavailable(RuntimeError):
    """The bridge failed; the call is logged as an error, never scored as an answer."""


def bridge_learner(run_dir: Path):
    empty = run_dir / "learner-empty"
    empty.mkdir(parents=True, exist_ok=True)
    counter = [0]

    def ask(prompt: str) -> str:
        counter[0] += 1
        prompt_file = run_dir / "prompts" / f"call-{counter[0]:03d}.txt"
        prompt_file.parent.mkdir(exist_ok=True)
        prompt_file.write_text(BRIEF + prompt, encoding="utf-8")
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BRIDGE),
             "-Tool", "agy", "-PromptFile", str(prompt_file), "-WorkDir", str(empty), "-ReplyOnly"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        if result.returncode != 0:
            raise LearnerUnavailable(f"bridge exited {result.returncode}: {result.stderr.strip()[-300:]}")
        text = result.stdout.strip()
        if text.startswith("{"):  # the bridge sometimes returns the provider's JSON envelope
            try:
                text = json.loads(text.split("\n[full log")[0]).get("response", text)
            except json.JSONDecodeError:
                pass
        return re.sub(r"\n\[full log:.*$", "", text, flags=re.S).strip()

    return ask


def first_answer(reply: str) -> str:
    """The first non-empty line, without labels, quotes or a trailing full stop."""
    for line in reply.splitlines():
        line = re.sub(r"^\s*(answer|my answer|meaning|note)\s*:\s*", "", line.strip(), flags=re.I)
        line = line.strip().strip("`*\"'").strip().rstrip(".").strip("\"'")
        if line:
            return line
    return ""


def split_lesson(text: str) -> tuple[str, str]:
    """Everything up to and including the question line, then the rest."""
    lines = text.split("\n")
    q = next(i for i, line in enumerate(lines) if line.startswith("Question:"))
    return "\n".join(lines[:q + 1]), "\n".join(lines[q + 1:])


def matches(answer: str, accepted) -> bool:
    return " ".join(answer.split()).casefold() in {" ".join(a.split()).casefold() for a in accepted}


def pretest(pack, ask, log, forced: bool = False) -> list[dict]:
    rng = random.Random(SEED)
    units = list(pack.units)
    rng.shuffle(units)
    items = []
    for start in range(0, len(units), PRETEST_BATCH):
        batch = units[start:start + PRETEST_BATCH]
        # The forced form allows no abstention, so 0% cannot be met by answering "unknown".
        prompt = ("Before any lessons: for each invented word below, give your best guess at its English "
                  + ("meaning. You must guess a real English word or short phrase for every one; 'unknown' "
                     "is not allowed. " if forced else "meaning, or 'unknown'. ")
                  + "Reply with exactly one line per word in the form word: meaning.\n\n"
                  + "\n".join(u.target.word for u in batch))
        try:
            reply = ask(prompt)
        except LearnerUnavailable as error:
            log.append(dict(kind="pretest", error=str(error)))
            reply = ""
        log.append(dict(kind="pretest", words=[u.target.word for u in batch], reply=reply))
        guesses = {}
        for line in reply.splitlines():
            word, _, guess = line.partition(":")
            guesses[word.strip().strip("*`").casefold()] = first_answer(guess)
        for u in batch:
            guess = guesses.get(u.target.word.casefold(), "")
            items.append(dict(word=u.target.word, guess=guess,
                              correct=matches(guess, u.check.answer_key.accepted)))
    return items


def course(pack, ask, log, store_path: Path) -> dict:
    rng = random.Random(SEED + 1)
    clock = [START]
    store = SQLiteStore(store_path)
    notebook: list[tuple[str, str]] = []  # (unit_id, the learner's own note), most recent last
    try:
        store.confirm_consent(START)
        with store.connection:
            store.connection.execute("INSERT INTO learner_identity VALUES (1, 'ai-learner-antigravity-1')")
        engine = MicroUnitEngine(pack, store, lambda: clock[0], daily_limit=UNITS_PER_DAY, contrast=ORDER_V1)
        for day in range(29):
            clock[0] = START + timedelta(days=day, hours=12)
            for _ in range(UNITS_PER_DAY if day < STUDY_DAYS else 0):
                exposures = engine._exposures()
                # Study visits take units in the engine's order (unfinished first); checks wait for 18:00.
                unit = next((u for u in engine._ordered_units() if u.id in exposures
                             and not exposures[u.id]["completed_at"]), None) or next(
                    (u for u in engine._ordered_units() if u.id not in exposures), None)
                if unit is None:
                    break
                lesson = engine.start_unit(unit.id)
                first, rest = split_lesson(lesson["lesson"])
                entry = dict(kind="lesson", day=day, unit=lesson["unit_id"], method=lesson["method_id"])
                try:
                    reply = ask("Lesson, part 1 of 2:\n" + first + "\n\nAnswer the question in one short line.")
                    note = first_answer(ask(
                        "Lesson, part 1 of 2 (as you saw it):\n" + first + "\n\nYour answer was: "
                        + first_answer(reply) + "\n\nLesson, part 2 of 2:\n" + rest
                        + "\n\nWrite one short line for your own notebook (at most 15 words)."))
                    notebook.append((lesson["unit_id"], note))
                    entry.update(reply=first_answer(reply), note=note)
                except LearnerUnavailable as error:
                    # The learner never saw the lesson: leave it unfinished so it resumes next visit.
                    log.append(dict(entry, error=str(error)))
                    break
                engine.complete_unit(lesson["unit_id"])
                log.append(entry)
                clock[0] += timedelta(minutes=5)
            clock[0] = START + timedelta(days=day, hours=18)
            while (activity := engine.next_activity()) is not None and activity["kind"] == "check":
                kept = [note for _, note in notebook[-NOTEBOOK_CAP:] if rng.random() >= OMIT]
                rng.shuffle(kept)
                prompt = ("Your notebook (your own notes, some may be missing):\n"
                          + ("\n".join(f"- {n}" for n in kept) or "(empty)")
                          + "\n\nQuestion: " + activity["prompt"]
                          + "\nReply with the English meaning only, on one line.")
                entry = dict(kind="check", day=day, unit=activity["unit_id"], notebook_lines=len(kept))
                try:
                    answer = first_answer(ask(prompt))
                except LearnerUnavailable as error:
                    log.append(dict(entry, error=str(error)))
                    break  # leave the check unanswered; never score a bridge failure
                result = engine.answer_check(activity["unit_id"], answer, outside_study="none")
                log.append(dict(entry, answer=answer, score=result["score_status"],
                                classification=result["classification"]))
                clock[0] += timedelta(minutes=2)
        day_zero = datetime.fromisoformat(engine.contrast_status()["day_zero"])
        clock[0] = day_zero + timedelta(days=28, hours=1)
        return engine.contrast_status()
    finally:
        store.close()


def report_html(result: dict) -> str:
    pre = result["pretest"]
    correct = sum(i["correct"] for i in pre)
    status = result.get("status")
    look = status["looks"][-1] if status and status["looks"] else None
    rows = "".join(f"<tr><td>{html.escape(i['word'])}</td><td>{html.escape(i['guess'])}</td>"
                   f"<td>{'yes' if i['correct'] else ''}</td></tr>" for i in pre)
    arms = "" if not look else "".join(
        f"<tr><th scope=row>{html.escape(status[role])}</th><td>{s}</td><td>{f}</td><td>{s / max(1, s + f):.0%}</td></tr>"
        for role, (s, f) in ((r, look["counts"][r]) for r in ("baseline", "variant")))
    pretest_ok = correct / len(pre) <= 0.05
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Learner Witness</title>
<style>
:root {{ --bg:#fbfbfa; --fg:#1d1d1f; --muted:#5f5f66; --rule:#e2e2e6; --pass:#1f7a4d; --fail:#b3261e; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#16161a; --fg:#ececf1; --muted:#a3a3ad; --rule:#2c2c33; --pass:#7fd1a3; --fail:#ff8a80; }} }}
body {{ background:var(--bg); color:var(--fg); font:16px/1.55 system-ui, sans-serif; margin:0; padding:24px 16px; }}
main {{ max-width:860px; margin:0 auto; }} .muted {{ color:var(--muted); font-size:.9em; }}
table {{ border-collapse:collapse; display:block; overflow-x:auto; margin:12px 0; }} th, td {{ border:1px solid var(--rule); padding:5px 9px; text-align:left; }}
.ok {{ color:var(--pass); font-weight:700; }} .bad {{ color:var(--fail); font-weight:700; }}
</style></head><body><main>
<h1>AI learner witness: order-v1</h1>
<p class="muted">One model (Antigravity), reported on its own; not evidence about people. {result['calls']} bridge calls, {result['errors']} errors, {result['seconds']:.0f} s. Memory rule: the learner's own one-line notes, the {NOTEBOOK_CAP} most recent, each omitted with probability {OMIT} and shuffled on every check call; check prompts, keys and correctness never enter the notebook.</p>
<h2>Zero-shot pretest</h2>
<p class="{'ok' if pretest_ok else 'bad'}">{correct} of {len(pre)} correct ({correct / len(pre):.1%}); gate limit 5%: {'pass' if pretest_ok else 'FAIL'}.</p>
<h2>Day-28 contrast result</h2>
<p>{html.escape(str(status['outcome'])) if status else 'not run'}{f" (winner {html.escape(str(status['winner']))}, day {status['decision_day']})" if status and status['winner'] else ''}</p>
<table><thead><tr><th>Method</th><th>Matched the draft key</th><th>Did not</th><th>Share</th></tr></thead><tbody>{arms}</tbody></table>
<details><summary>Pretest items</summary><table><thead><tr><th>Word</th><th>Guess</th><th>Correct</th></tr></thead><tbody>{rows}</tbody></table></details>
</main></body></html>
"""


def run(run_dir: Path, ask, pretest_only: bool = False, forced: bool = False) -> dict:
    run_dir.mkdir(parents=True, exist_ok=True)
    if any(run_dir.glob("*.sqlite3")) or (run_dir / "result.json").exists():
        raise SystemExit(f"{run_dir} holds an earlier run: use a fresh run directory")
    pack = load_micro_unit_pack(PACK)
    log: list[dict] = []
    calls = [0]

    def counted(prompt):
        calls[0] += 1
        return ask(prompt)

    started = time.monotonic()
    result = dict(pretest=pretest(pack, counted, log, forced), pretest_forced=forced, status=None)
    if not pretest_only:
        result["status"] = course(pack, counted, log, run_dir / "learner.sqlite3")
    result.update(calls=calls[0], errors=sum("error" in e for e in log), seconds=time.monotonic() - started,
                  notebook_cap=NOTEBOOK_CAP, omit=OMIT, seed=SEED)
    (run_dir / "transcript.json").write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")
    (run_dir / "result.json").write_text(json.dumps(result, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    (run_dir / "ai-learner-witness.html").write_text(report_html(result), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--pretest-only", action="store_true")
    parser.add_argument("--forced-guess", action="store_true", help="the pretest forbids 'unknown' (Grok P1)")
    args = parser.parse_args()
    if ROOT in args.run_dir.resolve().parents:
        parser.error("--run-dir must be outside the repository")
    result = run(args.run_dir, bridge_learner(args.run_dir), args.pretest_only, args.forced_guess)
    correct = sum(i["correct"] for i in result["pretest"])
    print(f"pretest {correct}/{len(result['pretest'])}; outcome "
          f"{result['status'] and result['status']['outcome']}; {result['calls']} calls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

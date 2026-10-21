"""Drive the real Foreman preview with an AI agent acting as the learner.

SIMULATION ONLY. The learner is a language model that already knows Python, so
nothing here is evidence of human learning, retention, or method effect.

Each round shows the agent only what a learner would see: a lesson, or one
question with its choices. The agent answers from an empty folder through the
agent bridge, with no repository access, so it cannot read the answer keys. It
keeps a notebook of its own lesson takeaways and whether each earlier answer
matched; keys and correct answers are never added to it.

The clock is simulated. Visits are spread over days 0 to 10 so the day-1 and
day-7 delayed checks come due. Everything is written to --run-dir, which must be
outside the repository.

    py scripts/simulated_learner_run.py --run-dir C:\\path\\to\\run --rounds 50
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aesop_lab.foreman import Preview  # noqa: E402

BRIDGE = Path.home() / ".claude/skills/agent-bridge/ask.ps1"
START = datetime(2026, 10, 21, 9, 0, tzinfo=timezone.utc)
# (day offset, round budget). Totals 50; later visits leave room for delayed checks.
VISITS = ((0, 14), (1, 9), (2, 5), (4, 4), (7, 10), (8, 4), (10, 4))

LEARNER_BRIEF = (
    "You are role-playing a beginner learning Python functions and recursion in a "
    "tutoring app. Answer as yourself, honestly, without running code or opening, "
    "reading or searching any files, and without using any tools. Reply in plain "
    "text only.\n\n"
)


def ask_learner(prompt: str, run_dir: Path, round_no: int, model: str | None) -> str:
    prompt_file = run_dir / "prompts" / f"round-{round_no:02d}.txt"
    prompt_file.parent.mkdir(exist_ok=True)
    prompt_file.write_text(LEARNER_BRIEF + prompt, encoding="utf-8")
    command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BRIDGE),
               "-Tool", "agy", "-PromptFile", str(prompt_file),
               "-WorkDir", str(run_dir / "learner-empty"), "-ReplyOnly"]
    if model:
        command += ["-Model", model]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=900)
    text = result.stdout.strip()
    # The bridge sometimes returns the provider's JSON envelope.
    if text.startswith("{"):
        try:
            text = json.loads(text.split("\n[full log")[0]).get("response", text)
        except json.JSONDecodeError:
            pass
    return re.sub(r"\n\[full log:.*$", "", text, flags=re.S).strip()


def first_line(reply: str) -> str:
    for line in reply.splitlines():
        line = re.sub(r"^(answer|my answer)\s*:\s*", "", line.strip(), flags=re.I)
        line = line.strip().strip("`").strip()
        if line:
            return line
    return ""


def match_choice(answer: str, choices: list[str]) -> str | None:
    """Map a reply onto one listed choice: exact, quote/case-insensitive, or 'A'/'1'."""
    def norm(text: str) -> str:
        return " ".join(text.strip().strip("`'\"").split()).lower()
    for choice in choices:
        if norm(answer) == norm(choice):
            return choice
    index = re.fullmatch(r"\(?([A-Za-z]|\d)[).:]?", answer.strip())
    if index:
        key = index.group(1)
        position = ord(key.lower()) - ord("a") if key.isalpha() else int(key) - 1
        if 0 <= position < len(choices):
            return choices[position]
    letter_prefix = re.match(r"^\(?[A-Za-z]\)?[.:)]\s*(.+)$", answer.strip())
    return match_choice(letter_prefix.group(1), choices) if letter_prefix else None


def question_prompt(activity: dict, notebook: list[str]) -> str:
    lines = ["Your notebook so far (your own notes, not answers):"]
    lines += [f"- {note}" for note in notebook[-30:]] or ["- (empty)"]
    lines += ["", "The app shows this question:", activity["prompt"]]
    if activity.get("body"):
        lines += ["", "```python", activity["body"], "```"]
    if activity.get("choices"):
        lines += ["", "Choices (answer with the exact text of one choice):"]
        lines += [f"- {choice}" for choice in activity["choices"]]
    lines += ["", "Reply with ONLY your answer on the first line. Do not explain."]
    return "\n".join(lines)


def lesson_prompt(lesson: dict, notebook: list[str]) -> str:
    parts = ["Your notebook so far:"] + ([f"- {n}" for n in notebook[-30:]] or ["- (empty)"])
    parts += ["", f"The app shows this lesson: {lesson['title']}", "", lesson["body"]]
    if lesson.get("diagram"):
        parts += ["", "Labeled diagram:", lesson["diagram"]]
    parts += ["", "Study it. Then reply with ONE line: the most important thing you "
              "want to remember, in your own words."]
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=50)
    parser.add_argument("--model", default=None, help="optional agy model name")
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    if ROOT in run_dir.parents or run_dir == ROOT:
        parser.error("--run-dir must be outside the repository")
    (run_dir / "learner-empty").mkdir(parents=True, exist_ok=True)
    db = run_dir / "simulated-learner.sqlite3"
    if db.exists():
        parser.error(f"{db} exists: use a fresh run directory")

    clock = [START]
    preview = Preview(db, now=lambda: clock[0])
    transcript = (run_dir / "transcript.jsonl").open("a", encoding="utf-8")
    notebook: list[str] = []
    round_no = 0
    preview.consent()  # simulated learner; consent-v1 is recorded like any learner's
    try:
        for day, budget in VISITS:
            clock[0] = START + timedelta(days=day)
            for _ in range(budget):
                if round_no >= args.rounds:
                    break
                overview = preview.overview()
                recommendation = overview["pathRecommendation"]
                cid = recommendation["conceptId"]
                entry = {"round": round_no + 1, "day": day, "at": clock[0].isoformat(),
                         "concept": cid, "action": recommendation["action"],
                         "reason": recommendation["reason"]}
                if recommendation["action"] == "lesson":
                    lesson = preview.lesson(cid)
                    started = time.monotonic()
                    reply = ask_learner(lesson_prompt(lesson, notebook), run_dir, round_no + 1, args.model)
                    note = first_line(reply)
                    notebook.append(f"[{lesson['title']}] {note}")
                    preview.complete_lesson(cid)
                    entry.update(kind="lesson", method=(lesson.get("method") or {}).get("conditionId"),
                                 learnerNote=note, seconds=round(time.monotonic() - started))
                else:
                    session = preview.session(cid, mode="recommended")
                    activity = session.get("activity")
                    if not activity:
                        entry.update(kind="caught_up")
                        transcript.write(json.dumps(entry) + "\n")
                        transcript.flush()
                        break  # nothing to do this visit; wait for the next day
                    started = time.monotonic()
                    reply = ask_learner(question_prompt(activity, notebook), run_dir, round_no + 1, args.model)
                    answer = first_line(reply)
                    entry.update(kind="question", activityId=activity["id"], heldOut=activity["heldOut"],
                                 checkDelayDays=activity.get("checkDelayDays"), answer=answer,
                                 seconds=round(time.monotonic() - started))
                    if answer and activity.get("choices"):
                        matched = match_choice(answer, activity["choices"])
                        entry["answerAsChoice"] = matched
                        answer = matched or ""
                        if not matched:
                            entry["error"] = "reply matched none of the listed choices"
                    if not answer:
                        entry.setdefault("error", "no answer from learner")
                    else:
                        draft = str(uuid4())
                        preview.first_answer({"conceptId": cid, "activityId": activity["id"],
                                              "draftId": draft, "answer": answer})
                        result = preview.submit({"draftId": draft, "outsideStudy": "none",
                                                 "activeSeconds": entry["seconds"]})
                        entry["scoreStatus"] = result.get("scoreStatus")
                        label = "matched the draft key" if result.get("scoreStatus") == "correct" else (
                            "did not match the draft key" if result.get("scoreStatus") == "incorrect"
                            else "was saved for self review")
                        notebook.append(f"Earlier answer on '{activity['prompt'][:60]}' {label}.")
                round_no += 1
                transcript.write(json.dumps(entry) + "\n")
                transcript.flush()
                clock[0] += timedelta(minutes=4)
                print(f"round {round_no}: day {day} {entry['kind']} {cid} "
                      f"{entry.get('scoreStatus', '')}", flush=True)
            if round_no >= args.rounds:
                break
        clock[0] = START + timedelta(days=15)  # every started concept's window has closed
        (run_dir / "export.json").write_text(json.dumps(preview.export(), indent=1, default=str),
                                             encoding="utf-8")
        findings = preview.experiment_findings()
        (run_dir / "findings.json").write_text(json.dumps(findings, indent=1, default=str),
                                               encoding="utf-8")
        print(f"done: {round_no} rounds; status {findings.get('status')}", flush=True)
    finally:
        transcript.close()
        preview.store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

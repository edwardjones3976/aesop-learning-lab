"""Repeat the synthetic runbook journey; no recruitment or retained learner data.

Run with: py scripts/pilot_readiness_dry_run.py
All databases are fresh TemporaryDirectory files and are removed on exit.
Candidate keys are used only to drive deterministic software checks.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from dataclasses import replace
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aesop_lab.foreman import Preview, VERSION_BY_CONTENT
from aesop_lab.api.service import ApiError


def main():
    start = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
    with TemporaryDirectory(prefix="aesop-dry-run-") as directory:
        clock = [start]
        path = Path(directory) / "synthetic.sqlite3"
        p = Preview(path, now=lambda: clock[0])
        try:
            assert p.store.existing_learner_id() is None
            assert p.overview()["packVersion"] == "m2-draft.11"
            assert p.export()["experimentAssignments"] == []
            ids = p.pack.learning_order()

            def day(value):
                clock[0] = start + timedelta(days=value)

            def save(cid):
                activity = p.session(cid)["activity"]
                item = next(i for i in p.pack.items if i.id == activity["id"])
                body = {"conceptId": cid, "activityId": activity["id"],
                        "draftId": str(uuid4()), "answer": item.answer_key.accepted[0]}
                assert p.first_answer(body)["saved"]
                return activity, body

            def answer(cid, outside="none", hint=False, wrong=False):
                activity = p.session(cid)["activity"]
                if wrong:
                    item = next(i for i in p.pack.items if i.id == activity["id"])
                    body = {"conceptId": cid, "activityId": activity["id"],
                            "draftId": str(uuid4()), "answer": next(
                                (c for c in activity["choices"] if c != item.answer_key.accepted[0]), "deliberately wrong")}
                    p.first_answer(body)
                else:
                    activity, body = save(cid)
                if hint:
                    assert p.hint({"draftId": body["draftId"]})["level"] == "nudge"
                result = p.submit({"draftId": body["draftId"], "outsideStudy": outside})
                assert result["assisted"] == hint
                return activity, result

            for cid in ids:
                if cid == ids[4]:
                    day(.25)  # a later lesson has its own return windows
                lesson = p.lesson(cid)
                assert lesson["method"]["protocolVersion"] == "v8"
                p.complete_lesson(cid)
            assert len(p.export()["experimentAssignments"]) == 5
            print("lesson notice:", lesson["experimentNotice"])
            # Merely requesting a session never saves an unsaved answer.
            p.session(ids[0])
            assert p.store.open_draft(ids[0]) is None
            _, saved = save(ids[0])
            p.store.close()
            p = Preview(path, now=lambda: clock[0])
            assert p.session(ids[0])["draft"]["firstAnswer"] == saved["answer"]
            changed = {**saved, "answer": "replacement"}
            try:
                p.first_answer(changed)
                raise AssertionError("first answer was rewritten")
            except ApiError as error:
                assert error.status == 409
                print("rewrite rejection:", str(error))
            p.submit({"draftId": saved["draftId"], "outsideStudy": "none"})
            for cid in ids[1:4]:
                answer(cid)
            answer(ids[4], hint=True)  # no qualifying independent practice
            day(1.001)
            assert p.overview()["concepts"][0]["signals"]["reviewSchedule"]["status"] == "due"
            assert not p.session(ids[4])["activity"]["heldOut"]
            for cid in ids[:2]:
                a, _ = answer(cid, wrong=True)  # wrong day 1 still unlocks week
                assert a["checkDelayDays"] == 1
            day(2.001)
            assert p.overview()["concepts"][2]["signals"]["reviewSchedule"]["status"] == "overdue"
            assert not p.session(ids[4])["activity"]["heldOut"]
            day(6.999)
            assert not p.session(ids[0])["activity"]["heldOut"]
            day(7.001)
            for cid, outside in zip(ids[:2], ("none", "some")):
                a, _ = answer(cid, outside=outside)
                assert a["checkDelayDays"] == 7
                print("week reason:", p.session(cid).get("recommendation"))
            # Unused day-1 check can unlock a week check in the same visit.
            a, _ = answer(ids[2], wrong=True)
            assert a["checkDelayDays"] == 1
            assert p.session(ids[2])["activity"]["checkDelayDays"] == 7
            print("same-visit week reason:", p.session(ids[2])["recommendation"]["reason"])
            day(14.001)
            a, _ = answer(ids[3])
            assert a["checkDelayDays"] == 1
            a, result = answer(ids[3])
            assert a["checkDelayDays"] == 7
            count = len(p.export()["attempts"])
            assert p.submit({"draftId": result["attemptId"]}) == result
            assert len(p.export()["attempts"]) == count
            day(14.251)  # every started concept's own window has now closed
            exported = p.export()
            assert exported["derived"]["overview"] == p.overview()
            assert exported["attempts"] and exported["experimentExposures"]
            finding = exported["derived"]["overview"]["experiment"]
            observations = [o for arm in finding["arms"].values() for o in arm["observations"]]
            actual = {o["conceptId"]: o["classification"] for o in observations}
            assert actual == dict(zip(ids, ("provisional", "contaminated", "missing", "late", "missing"))), actual
            assert finding["status"] == "insufficient_evidence"
            assert all(arm["eligible"] == 0 for arm in finding["arms"].values())
            print("export classifications:", json.dumps(actual, sort_keys=True))
            print("raw export keys:", ", ".join(exported))
            print("delays:", json.dumps([{k: v for k, v in o.items() if k in
                ("conceptId", "classification", "elapsedDays", "elapsedSeconds")} for o in observations]))
            # Early is unreachable through the normal scheduler. Exercise the
            # same classifier used by export with an IN-MEMORY fixture only.
            # The persisted run's clocks and answers above remain untouched.
            protocol, _, Exposure, analyze = VERSION_BY_CONTENT["v11"].comparison.load()
            exposures = tuple(Exposure(r["concept_id"], r["content_version"], r["condition_id"],
                datetime.fromisoformat(r["exposed_at"]), tuple(json.loads(r["encountered_family_ids"])),
                r["protocol_id"], r["protocol_version"], datetime.fromisoformat(r["completed_at"]))
                for r in p.store.list_exposures())
            attempts = tuple(a for cid in ids for a in p.store.list_attempts(cid))
            primary_id = next(o["firstAttemptId"] for o in observations if o["conceptId"] == ids[0])
            fixture = tuple(replace(a, occurred_at=start + timedelta(days=6.999))
                            if a.id == primary_id else a for a in attempts)
            analyzed = analyze(p.store.list_assignments(protocol.id), exposures, fixture,
                {i.activity.id: i.activity for i in p.pack.items},
                learner_id=p.store.existing_learner_id(), now=clock[0])
            assert next(o["classification"] for arm in analyzed["arms"].values()
                        for o in arm["observations"] if o["conceptId"] == ids[0]) == "early"
            assert p.export() == exported
            print("early: classifier fixture PASS; normal scheduler refuses week before day 7")
            assert p.delete_data()["deleted"]
            p.store.close()
            p = Preview(path, now=lambda: clock[0])
            assert p.overview()["deleted"]
            assert p.export()["attempts"] == []
            assert p.store.existing_learner_id() is None
            try:
                p.lesson(ids[0])
                raise AssertionError("deleted learner enrolled")
            except ApiError as error:
                assert error.status == 409 and error.code == "learner_deleted"
                print("deleted enrollment:", error.status, error.code)
            print("PASS: recovery, first-answer lock, hints, due/overdue, prerequisites, same-visit week, export, late, deletion")
        finally:
            p.store.close()


if __name__ == "__main__":
    main()

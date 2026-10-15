"""Loopback-only development preview of the draft Python content pack."""

from __future__ import annotations

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from aesop_lab.api.service import ApiError, CatalogItem, LearningService
from aesop_lab.assessment import AnswerKey, Hint, HintLadder, ItemSpec, Rubric, RubricCriterion, assess
from aesop_lab.content import load_pack
from aesop_lab.domain.models import HintLevel
from aesop_lab.storage.sqlite import SQLiteStore

ROOT = Path(__file__).resolve().parents[2]
PACK_PATH = ROOT / "content/packs/python-functions-recursion/pack.json"
WEB = ROOT / "foreman_web"
DB = ROOT / ".local/foreman.sqlite3"
HOST = "127.0.0.1"
PORT = 8775


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _catalog_item(item) -> CatalogItem:
    rubric = None
    if item.rubric:
        rubric = Rubric(item.rubric.id, tuple(
            RubricCriterion(c.id, c.description) for c in item.rubric.criteria
        ), annotated_example=item.rubric.annotated_example,
            common_mistakes=item.rubric.common_mistakes)
    spec = ItemSpec(
        item.activity, choices=item.choices,
        answer_key=AnswerKey(item.answer_key.accepted) if item.answer_key else None,
        rubric=rubric,
        hints=HintLadder(tuple(Hint(h.level, h.text) for h in item.hints)),
    )
    return CatalogItem(spec, item.prompt, item.body)


class Preview:
    def __init__(self, db: Path = DB) -> None:
        self.pack = load_pack(PACK_PATH)
        if self.pack.status != "draft" or any(
            item.answer_key and item.answer_key.status != "candidate" for item in self.pack.items
        ):
            raise RuntimeError("This preview is only for a draft pack with candidate keys")
        self.store = SQLiteStore(db)
        self.services = {
            concept.id: LearningService(
                self.store, concept,
                tuple(_catalog_item(item) for item in self.pack.items_for(concept.id)),
                reviewed=False, allow_development_fixtures=True,
            ) for concept in self.pack.concepts
        }

    def overview(self) -> dict:
        order = self.pack.learning_order()
        def summary(cid: str) -> dict:
            attempts = self.store.list_attempts(cid)
            return {
                "attempts": len(attempts),
                "unassistedCorrect": sum(a.score_status.value == "correct" and a.unassisted for a in attempts),
                "hintAssisted": sum(not a.unassisted for a in attempts),
                "needsReview": sum(a.score_status.value == "ungraded" for a in attempts),
                "recentOutcome": attempts[-1].score_status.value if attempts else None,
            }
        return {"developmentOnly": True, "packStatus": self.pack.status,
                "concepts": [{"id": cid, "title": self.pack.concept(cid).title,
                              "lessonComplete": self.store.lesson_completed_at(
                                  cid, self.pack.concept(cid).content_version) is not None,
                              "signals": summary(cid)}
                             for cid in order]}

    def lesson(self, cid: str) -> dict:
        service = self._service(cid)
        lesson = next(x for x in self.pack.lessons if x.concept_id == cid)
        sources = {s.id: s for s in self.pack.sources}
        return {"conceptId": cid, "title": lesson.title, "body": lesson.body,
                "completed": self.store.lesson_completed_at(
                    cid, service.concept.content_version) is not None,
                "sources": [{"title": sources[sid].title, "url": sources[sid].url}
                            for sid in lesson.source_ids]}

    def complete_lesson(self, cid: str) -> dict:
        stamp = self._service(cid).complete_lesson()
        return {"completedAt": stamp.isoformat(), "developmentOnly": True}

    def session(self, cid: str, mode: str = "recommended", available_minutes: int = 20) -> dict:
        service = self._service(cid)
        if mode not in ("recommended", "practice"):
            raise ApiError("validation_error", "Unknown practice mode.")
        if type(available_minutes) is not int or not 5 <= available_minutes <= 60:
            raise ApiError("validation_error", "Choose a session length from 5 to 60 minutes.")
        if self.store.lesson_completed_at(cid, service.concept.content_version) is None:
            return {"lessonRequired": True, "activity": None}
        draft = self.store.open_draft(cid)
        if draft:
            item = service.items[draft["activity_id"]]
            result = {"activity": item.public(), "recommendation": {"reason": "Resume your saved answer"},
                      "draft": {"id": draft["id"], "firstAnswer": draft["first_answer"],
                                "hintLevels": [x.value for x in self.store.hint_levels(draft["id"])]}}
        else:
            result = service.next_session(available_minutes, mode)
            result["draft"] = None
        if result.get("activity"):
            viewed = set(result["draft"]["hintLevels"]) if result["draft"] else set()
            for hint in result["activity"]["hints"]:
                if hint["level"] not in viewed:
                    hint.pop("text")
        return result

    def first_answer(self, body: dict) -> dict:
        cid, aid, did, answer = (body.get(k) for k in
                                 ("conceptId", "activityId", "draftId", "answer"))
        service = self._service(cid)
        try:
            UUID(did, version=4)
        except (TypeError, ValueError, AttributeError):
            raise ApiError("validation_error", "A UUID draftId is required.") from None
        if not isinstance(answer, str) or not answer.strip() or len(answer) > 12000:
            raise ApiError("validation_error", "Enter an answer (up to 12,000 characters).")
        existing = self.store.get_draft(did)
        if existing:
            if (existing["activity_id"], existing["first_answer"]) != (aid, answer):
                raise ApiError("conflict", "This answer ID already belongs to another answer.", 409)
            return {"draftId": did, "saved": True}
        if self.store.open_draft(cid):
            raise ApiError("conflict", "Finish your saved answer first.", 409)
        session = self.session(cid, body.get("mode", "recommended"),
                               body.get("availableMinutes", 20))
        if not session.get("activity") or session["activity"]["id"] != aid:
            raise ApiError("activity_unavailable", "Choose the activity currently offered.", 409)
        item = service.items[aid]
        if item.spec.choices and answer not in item.spec.choices:
            raise ApiError("validation_error", "Choose one of the listed options.")
        self.store.save_draft(did, aid, service.concept.content_version, answer, _now())
        return {"draftId": did, "saved": True}

    def hint(self, body: dict) -> dict:
        draft, service, item = self._draft_item(body.get("draftId"))
        if draft["submitted_attempt_id"]:
            raise ApiError("conflict", "This answer is already submitted.", 409)
        viewed = self.store.hint_levels(draft["id"])
        current = viewed[-1] if viewed else HintLevel.NONE
        next_level = item.spec.hints.next_level(current)
        if next_level is None:
            raise ApiError("hint_exhausted", "All hints are open.", 409)
        self.store.save_hint(draft["id"], next_level, _now())
        revealed = next(h for h in item.spec.hints.hints if h.level == next_level)
        return {"level": next_level.value, "text": revealed.text}

    def submit(self, body: dict) -> dict:
        draft, service, item = self._draft_item(body.get("draftId"))
        if draft["response_json"]:
            return json.loads(draft["response_json"])
        levels = self.store.hint_levels(draft["id"])
        hint = levels[-1] if levels else HintLevel.NONE
        existing = next((a for a in self.store.list_attempts(service.concept.id)
                         if a.id == draft["id"]), None)
        if existing is not None:
            result = assess(item.spec, draft["first_answer"], hint)
            response = {"attemptId": existing.id, "scoreStatus": existing.score_status.value,
                        "gradingMethod": existing.grading_method,
                        "assisted": not existing.unassisted,
                        "nextReason": result.reason, "developmentOnly": True}
            if item.spec.rubric:
                rubric = item.spec.rubric
                response["rubric"] = {"id": rubric.id, "version": rubric.version,
                                      "criteria": [{"id": c.id, "description": c.description}
                                                   for c in rubric.criteria]}
            self.store.finish_draft(draft["id"], response)
            return response
        response = service.submit_attempt({
            "activityId": item.spec.activity.id,
            "contentVersion": item.spec.activity.content_version,
            "firstAnswer": draft["first_answer"], "hintLevel": hint.value,
            "confidence": body.get("confidence"), "outsideStudy": None,
            "outsideStudyDetail": None, "activeSeconds": body.get("activeSeconds", 0),
        }, attempt_id=draft["id"])
        self.store.finish_draft(draft["id"], response)
        return response

    def _service(self, cid) -> LearningService:
        if not isinstance(cid, str) or cid not in self.services:
            raise ApiError("not_found", "Concept was not found.", 404)
        return self.services[cid]

    def _draft_item(self, did):
        if not isinstance(did, str):
            raise ApiError("validation_error", "draftId is required.")
        draft = self.store.get_draft(did)
        if draft is None:
            raise ApiError("not_found", "Saved answer was not found.", 404)
        activity = self.store.get_activity(draft["activity_id"], draft["content_version"])
        service = self._service(activity.concept_id)
        return draft, service, service.items[activity.id]


def make_handler(preview: Preview):
    class Handler(BaseHTTPRequestHandler):
        def _check_origin(self) -> bool:
            host = self.headers.get("Host", "")
            if host not in (f"{HOST}:{PORT}", f"localhost:{PORT}"):
                self._json(403, {"error": "Invalid host"})
                return False
            if self.command == "POST" and self.headers.get("Origin") not in (
                f"http://{HOST}:{PORT}", f"http://localhost:{PORT}"):
                self._json(403, {"error": "Invalid origin"})
                return False
            return True

        def _json(self, status: int, data: dict):
            payload = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _dispatch(self):
            if not self._check_origin():
                return
            path = urlsplit(self.path).path
            query = parse_qs(urlsplit(self.path).query)
            try:
                if self.command == "GET":
                    if path == "/api/v2/overview":
                        return self._json(200, preview.overview())
                    if path == "/api/v2/lesson":
                        return self._json(200, preview.lesson(query.get("conceptId", [None])[0]))
                    if path == "/api/v2/session":
                        raw_minutes = query.get("availableMinutes", ["20"])[0]
                        if not raw_minutes.isdecimal():
                            raise ApiError("validation_error", "Session length must be a whole number.")
                        return self._json(200, preview.session(query.get("conceptId", [None])[0],
                                                               query.get("mode", ["recommended"])[0],
                                                               int(raw_minutes)))
                    if path == "/api/v2/export":
                        return self._json(200, preview.store.export_all())
                    files = {"/": ("index.html", "text/html"),
                             "/app.js": ("app.js", "text/javascript"),
                             "/theme-init.js": ("theme-init.js", "text/javascript"),
                             "/style.css": ("style.css", "text/css"),
                             "/icon.svg": ("icon.svg", "image/svg+xml")}
                    if path in files:
                        name, mime = files[path]
                        content = (WEB / name).read_bytes()
                        self.send_response(200)
                        self.send_header("Content-Type", mime + "; charset=utf-8")
                        self.send_header("Content-Length", str(len(content)))
                        self.send_header("X-Content-Type-Options", "nosniff")
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                        self.wfile.write(content)
                        return
                if self.command == "POST" and path.startswith("/api/v2/"):
                    if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                        raise ApiError("validation_error", "Send JSON.", 415)
                    size = int(self.headers.get("Content-Length", "0"))
                    if size < 2 or size > 30000:
                        raise ApiError("validation_error", "JSON body size is invalid.")
                    body = json.loads(self.rfile.read(size))
                    if not isinstance(body, dict):
                        raise ApiError("validation_error", "JSON body must be an object.")
                    routes = {"/api/v2/lesson-completions": lambda: preview.complete_lesson(body.get("conceptId")),
                              "/api/v2/first-answers": lambda: preview.first_answer(body),
                              "/api/v2/hints": lambda: preview.hint(body),
                              "/api/v2/attempts": lambda: preview.submit(body),
                              "/api/v2/self-reviews": lambda: preview._service(body.get("conceptId")).submit_self_review(body),
                              "/api/v2/revisions": lambda: preview._service(body.get("conceptId")).submit_revision(body),
                              "/api/v2/delete": lambda: (preview.store.delete_all() or {"deleted": True})}
                    if path in routes:
                        return self._json(200, routes[path]())
            except (ApiError, ValueError, json.JSONDecodeError) as exc:
                if isinstance(exc, ApiError):
                    return self._json(exc.status, {"error": exc.code, "message": exc.message})
                return self._json(400, {"error": "validation_error", "message": str(exc)})
            self._json(404, {"error": "not_found"})

        def do_GET(self):
            self._dispatch()

        def do_POST(self):
            self._dispatch()

    return Handler


def main() -> None:
    preview = Preview()
    print(f"Foreman preview: http://{HOST}:{PORT}/", flush=True)
    HTTPServer((HOST, PORT), make_handler(preview)).serve_forever()


if __name__ == "__main__":
    main()

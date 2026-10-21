"""Loopback-bound WSGI transport for the development application service."""

from __future__ import annotations

import json
import sqlite3
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

from .service import ApiError, LearningService


ALLOWED_UI_ORIGINS = ("http://127.0.0.1:8765", "http://localhost:8765")


def make_app(service: LearningService):
    def app(environ, start_response):
        origin = environ.get("HTTP_ORIGIN", "")
        cors = ([("Access-Control-Allow-Origin", origin), ("Vary", "Origin")]
                if origin in ALLOWED_UI_ORIGINS else [])
        try:
            method = environ["REQUEST_METHOD"]
            path = environ["PATH_INFO"]
            port = environ.get("SERVER_PORT", "8766")
            if environ.get("HTTP_HOST") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
                raise ApiError("forbidden_request", "Use the local API host.", 403)
            if (origin or method in ("POST", "DELETE")) and origin not in ALLOWED_UI_ORIGINS:
                raise ApiError("forbidden_request", "Origin is not allowed.", 403)
            if ((method == "GET" and path == "/api/v1/session/next") or
                    (method == "POST" and path in ("/api/v1/attempts",
                     "/api/v1/self-reviews", "/api/v1/answer-revisions"))):
                service.store.require_active_learner()
            if method == "OPTIONS" and path.startswith("/api/v1/"):
                status, payload = "204 No Content", {}
                cors += [("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS"),
                         ("Access-Control-Allow-Headers", "Content-Type")]
            elif method == "GET" and path == "/api/v1/export":
                payload, status = service.export_data(), "200 OK"
            elif method == "DELETE" and path == "/api/v1/data":
                payload, status = service.delete_data(), "200 OK"
            elif method == "GET" and path == "/api/v1/session/next":
                query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
                if any(len(values) != 1 for values in query.values()):
                    raise ApiError("validation_error", "Query parameters must appear once.")
                try:
                    minutes = int(query.get("availableMinutes", ["20"])[0])
                except ValueError:
                    raise ApiError("validation_error", "availableMinutes must be a whole number.") from None
                payload = service.next_session(minutes, query.get("mode", ["recommended"])[0])
                status = "200 OK"
            elif method == "POST" and path in (
                    "/api/v1/attempts", "/api/v1/self-reviews", "/api/v1/answer-revisions"):
                if environ.get("CONTENT_TYPE", "").split(";", 1)[0].strip().lower() != "application/json":
                    raise ApiError("validation_error", "Content-Type must be application/json.")
                try:
                    length = int(environ.get("CONTENT_LENGTH") or "0")
                    if length < 1 or length > 65536:
                        raise ValueError
                    body = json.loads(environ["wsgi.input"].read(length))
                except (ValueError, json.JSONDecodeError):
                    raise ApiError("validation_error", "A JSON request body is required.") from None
                if path == "/api/v1/attempts":
                    payload = service.submit_attempt(body)
                elif path == "/api/v1/self-reviews":
                    payload = service.submit_self_review(body)
                else:
                    payload = service.submit_revision(body)
                status = "201 Created"
            else:
                raise ApiError("not_found", "Endpoint was not found.", 404)
        except ApiError as exc:
            status = {400: "400 Bad Request", 403: "403 Forbidden", 404: "404 Not Found",
                      409: "409 Conflict", 503: "503 Service Unavailable"}.get(
                          exc.status, "400 Bad Request")
            payload = {"code": exc.code, "message": exc.message}
        except sqlite3.Error:
            status = "503 Service Unavailable"
            payload = {"code": "storage_unavailable",
                       "message": "Local records are unavailable right now."}
        data = json.dumps(payload).encode("utf-8")
        start_response(status, [("Content-Type", "application/json; charset=utf-8"),
                                ("Content-Length", str(len(data))),
                                ("Cache-Control", "no-store"), *cors])
        return [data]
    return app


def serve(service: LearningService, port: int = 8766) -> None:
    with make_server("127.0.0.1", port, make_app(service)) as server:
        server.serve_forever()

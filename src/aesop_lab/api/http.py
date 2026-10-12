"""Loopback-only WSGI transport for the local application service."""

from __future__ import annotations

import json
import sqlite3
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

from .service import ApiError, LearningService


def make_app(service: LearningService):
    def app(environ, start_response):
        try:
            method = environ["REQUEST_METHOD"]
            path = environ["PATH_INFO"]
            if method == "GET" and path == "/api/v1/session/next":
                query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
                if any(len(values) != 1 for values in query.values()):
                    raise ApiError("validation_error", "Query parameters must appear once.")
                try:
                    minutes = int(query.get("availableMinutes", ["20"])[0])
                except ValueError:
                    raise ApiError("validation_error", "availableMinutes must be a whole number.") from None
                payload = service.next_session(minutes, query.get("mode", ["recommended"])[0])
                status = "200 OK"
            elif method == "POST" and path == "/api/v1/attempts":
                try:
                    length = int(environ.get("CONTENT_LENGTH") or "0")
                    if length < 1 or length > 65536:
                        raise ValueError
                    body = json.loads(environ["wsgi.input"].read(length))
                except (ValueError, json.JSONDecodeError):
                    raise ApiError("validation_error", "A JSON attempt body is required.") from None
                payload = service.submit_attempt(body)
                status = "201 Created"
            else:
                raise ApiError("not_found", "Endpoint was not found.", 404)
        except ApiError as exc:
            status = {400: "400 Bad Request", 404: "404 Not Found",
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
                                ("Cache-Control", "no-store")])
        return [data]
    return app


def serve(service: LearningService, port: int = 8766) -> None:
    with make_server("127.0.0.1", port, make_app(service)) as server:
        server.serve_forever()

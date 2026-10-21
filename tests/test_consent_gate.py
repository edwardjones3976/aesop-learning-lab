"""Consent boundary, migration, and erasure regressions."""
from contextlib import closing
import gzip
import json
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from http.server import HTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from aesop_lab.api.service import ApiError
from aesop_lab.foreman import Preview, make_handler
from aesop_lab.storage.sqlite import SQLiteStore


class ConsentGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "learner.db"
        self.preview = Preview(self.path)
        self.addCleanup(self.preview.store.close)
        self.cid = self.preview.pack.learning_order()[0]

    def test_fresh_endpoints_are_gated_and_readers_create_no_rows(self):
        preview = self.preview
        before = preview.store.export_all()
        server = HTTPServer(("127.0.0.1", 0), make_handler(preview, port=0))
        port = server.server_port
        # The handler's host/origin checks use its configured port.
        server.RequestHandlerClass = make_handler(preview, port=port)
        # SQLite connections belong to their creating thread: serve requests on
        # this thread while a client thread drives the actual HTTP boundary.
        base = f"http://127.0.0.1:{port}"
        results = []
        errors = []
        routes = [("GET", "/api/v2/session"), ("GET", "/api/v2/personal-comparison")]
        routes += [("POST", "/api/v2/" + route) for route in (
            "lesson", "lesson-completions", "first-answers", "hints", "attempts",
            "self-reviews", "revisions", "overrides", "personal-comparison/enroll",
            "personal-comparison/start", "personal-comparison/complete",
            "personal-comparison/open", "personal-comparison/hint",
            "personal-comparison/answer", "personal-comparison/reveal",
            "personal-comparison/override")]
        def client():
            try:
                for method, route in routes:
                    data = b'{}' if method == "POST" else None
                    req = Request(base + route, data=data, method=method,
                                  headers={"Origin": base, "Content-Type": "application/json"})
                    try:
                        with urlopen(req, timeout=5) as response:
                            results.append((route, response.status, json.load(response)))
                    except HTTPError as exc:
                        results.append((route, exc.code, json.load(exc)))
            except Exception as exc:
                errors.append(exc)
        thread = threading.Thread(target=client)
        thread.start()
        server.timeout = 1
        try:
            while thread.is_alive():
                server.handle_request()
        finally:
            thread.join()
            server.server_close()
        self.assertEqual(errors, [])
        self.assertEqual(len(results), len(routes))
        for route, status, body in results:
            with self.subTest(route=route):
                self.assertEqual(status, 409)
                self.assertEqual(body["code"], "consent_required")
        self.assertTrue(preview.overview()["consentRequired"])
        self.assertEqual(preview.export()["learnerIdentity"], [])
        self.assertEqual(preview.store.export_all(), before)

    def test_v1_learning_endpoints_require_consent(self):
        from io import BytesIO
        from aesop_lab.api.http import make_app
        from aesop_lab.api.dev_fixture import CONCEPT, fixture_items
        from aesop_lab.api.service import LearningService
        service = LearningService(self.preview.store, CONCEPT, fixture_items(),
                                  allow_development_fixtures=True, reviewed=False)
        app = make_app(service)
        before = self.preview.store.export_all()
        for method, path in [("GET", "/api/v1/session/next"),
                             ("POST", "/api/v1/attempts"),
                             ("POST", "/api/v1/self-reviews"),
                             ("POST", "/api/v1/answer-revisions")]:
            with self.subTest(path=path):
                statuses = []
                body = b'{}'
                result = app({"REQUEST_METHOD": method, "PATH_INFO": path,
                              "HTTP_HOST": "127.0.0.1:8766", "SERVER_PORT": "8766",
                              "HTTP_ORIGIN": "http://127.0.0.1:8765",
                              "CONTENT_TYPE": "application/json", "CONTENT_LENGTH": "2",
                              "wsgi.input": BytesIO(body)},
                             lambda status, headers: statuses.append(status))
                self.assertEqual(statuses, ["409 Conflict"])
                self.assertEqual(json.loads(b''.join(result))["code"], "consent_required")
        self.assertEqual(self.preview.store.export_all(), before)

    def test_consent_then_lesson_enrolls_and_persists_version_timestamp(self):
        preview = self.preview
        preview.consent()
        consent = preview.export()["learnerConsent"]
        self.assertEqual(len(consent), 1)
        self.assertEqual(consent[0]["text_version"], "consent-v1")
        self.assertIsNotNone(datetime.fromisoformat(consent[0]["confirmed_at"]).tzinfo)
        self.assertIsNone(preview.store.existing_learner_id())
        preview.consent()
        self.assertEqual(preview.export()["learnerConsent"], consent)
        preview.lesson(self.cid)
        self.assertIsNotNone(preview.store.existing_learner_id())
        self.assertEqual(len(preview.export()["experimentAssignments"]), 1)
        self.assertEqual(len(preview.export()["experimentExposures"]), 1)

    def test_delete_restart_requires_consent_again(self):
        preview = self.preview
        preview.consent()
        preview.lesson(self.cid)
        preview.delete_data()
        self.assertEqual(preview.export()["learnerConsent"], [])
        for action in (preview.consent, lambda: preview.lesson(self.cid)):
            with self.assertRaises(ApiError) as error:
                action()
            self.assertEqual(error.exception.code, "learner_deleted")
        preview.restart()
        self.assertTrue(preview.overview()["consentRequired"])
        with self.assertRaises(ApiError) as error:
            preview.lesson(self.cid)
        self.assertEqual(error.exception.code, "consent_required")
        self.assertIsNone(preview.store.existing_learner_id())
        preview.consent()
        preview.lesson(self.cid)
        self.assertIsNotNone(preview.store.existing_learner_id())

    def legacy_path(self):
        path = Path(self.temp.name) / "v15.db"
        fixture = Path(__file__).parent / "fixtures/consent-v15.sqlite3.gz"
        path.write_bytes(gzip.decompress(fixture.read_bytes()))
        return path

    def test_v15_migration_preserves_every_row(self):
        path = self.legacy_path()
        with closing(sqlite3.connect(path)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 15)
            tables = [row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")]
            before = {table: connection.execute(f'SELECT * FROM "{table}"').fetchall()
                      for table in tables}
        self.assertTrue(before["learner_identity"])
        self.assertTrue(before["experiment_exposures"])
        with SQLiteStore(path) as store:
            self.assertEqual(store.connection.execute("PRAGMA user_version").fetchone()[0], 19)
            for table, rows in before.items():
                with self.subTest(table=table):
                    self.assertEqual([tuple(row) for row in store.connection.execute(
                        f'SELECT * FROM "{table}"')], rows)
            self.assertEqual(store.export_all()["learnerConsent"][0]["text_version"], "legacy-pre-gate")

    def test_existing_pre_gate_learner_opens_and_works(self):
        preview = Preview(self.legacy_path())
        self.addCleanup(preview.store.close)
        self.assertFalse(preview.overview()["consentRequired"])
        cid = preview.pack.learning_order()[0]
        preview.lesson(cid)
        preview.complete_lesson(cid)
        self.assertIsNotNone(preview.session(cid)["activity"])


class ConsentMigrationAndStartupTests(unittest.TestCase):
    """Cursor's #57 findings: history without an identity, the v1 dev server, the overview."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "learner.db"

    def _as_v15_with_completion_only(self):
        # Simulate a pre-gate v1-v3 learner: lesson history but no identity row.
        with SQLiteStore(self.path):
            pass
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO lesson_completions VALUES (?, ?, ?)",
                       ("function-definition-and-return", "v1", "2026-01-01T00:00:00+00:00"))
            self.assertIsNone(db.execute("SELECT 1 FROM learner_identity").fetchone())
            db.execute("DROP TABLE learner_consent")
            db.execute("PRAGMA user_version = 15")

    def test_history_without_identity_migrates_as_legacy_consent(self):
        self._as_v15_with_completion_only()
        with SQLiteStore(self.path) as store:
            self.assertTrue(store.has_consent())
            row = store.connection.execute("SELECT text_version FROM learner_consent").fetchone()
            self.assertEqual(row[0], "legacy-pre-gate")

    def test_empty_v15_database_still_requires_consent(self):
        with SQLiteStore(self.path):
            pass
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DROP TABLE learner_consent")
            db.execute("PRAGMA user_version = 15")
        with SQLiteStore(self.path) as store:
            self.assertFalse(store.has_consent())

    def test_overview_before_consent_is_a_flag_not_an_error(self):
        preview = Preview(self.path)
        self.addCleanup(preview.store.close)
        overview = preview.overview()
        self.assertTrue(overview["consentRequired"])
        self.assertIsNone(preview.store.existing_learner_id())

    def test_pre_gate_v1_learner_keeps_working_through_preview(self):
        # Cursor's reproduction: a v15 database with a v1 lesson completion and no
        # identity must open, show no consent screen, and keep its schedule.
        self._as_v15_with_completion_only()
        preview = Preview(self.path)
        self.addCleanup(preview.store.close)
        overview = preview.overview()
        self.assertFalse(overview["consentRequired"])
        self.assertEqual(overview["packVersion"], preview.pack.pack_version)
        self.assertTrue(any(c["lessonComplete"] for c in overview["concepts"]))

    def test_v1_development_server_starts(self):
        import subprocess, sys, os
        env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
        proc = subprocess.Popen(
            [sys.executable, "-m", "aesop_lab.api", "--development-fixtures",
             "--db", str(Path(self.temp.name) / "dev.sqlite3"), "--port", "0"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        try:
            line = proc.stdout.readline()
            self.assertIn("Development fixture API", line, line)
        finally:
            proc.kill()
            proc.wait(timeout=10)
            proc.stdout.close()

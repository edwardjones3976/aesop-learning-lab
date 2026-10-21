"""Run bounded deliberate breaks; restore source bytes after each browser/Node check.

Run after normal suites (never concurrently): PYTHONPATH=src python scripts/check_consent_breaks.py
No databases outside temporary test directories are touched.
"""
from contextlib import redirect_stderr
from io import StringIO
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
from aesop_lab.foreman import Preview
from aesop_lab.storage.sqlite import SQLiteStore
from test_consent_gate import ConsentGateTests


def python_break(label, test, target, replacement):
    output = StringIO()
    with patch.object(target[0], target[1], replacement), redirect_stderr(output):
        result = unittest.TextTestRunner(stream=output).run(ConsentGateTests(test))
    if result.wasSuccessful():
        raise RuntimeError(f"SURVIVED: {label}")
    print(f"KILLED: {label} ({len(result.failures)} failures, {len(result.errors)} errors)", flush=True)


def source_break(label, relative, old, new, command, cwd=ROOT):
    path = ROOT / relative
    original = path.read_bytes()
    text = original.decode("utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"Expected one mutation target: {label}")
    try:
        path.write_text(text.replace(old, new), encoding="utf-8")
        env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True)
        if result.returncode == 0:
            raise RuntimeError(f"SURVIVED: {label}")
        # Guard against unrelated tool/setup errors masquerading as a kill.
        output = result.stdout + result.stderr
        if "AssertionError" not in output and "failed" not in output and "fail 1" not in output:
            raise RuntimeError(f"Unrecognized failure for {label}: {output[-2000:]}")
        print(f"KILLED: {label} (exit {result.returncode})", flush=True)
    finally:
        path.write_bytes(original)


def main():
    python_break("v2 enrollment guard bypass", "test_fresh_endpoints_are_gated_and_readers_create_no_rows",
                 (SQLiteStore, "require_active_learner"), lambda self: None)
    python_break("v1 guard bypass", "test_v1_learning_endpoints_require_consent",
                 (SQLiteStore, "require_active_learner"), lambda self: None)
    python_break("confirmation fails to persist", "test_consent_then_lesson_enrolls_and_persists_version_timestamp",
                 (Preview, "consent"), lambda self: {})
    python_break("legacy learner blocked", "test_existing_pre_gate_learner_opens_and_works",
                 (SQLiteStore, "has_consent"), lambda self: False)
    original_migrate = SQLiteStore._migrate
    def destructive_migrate(self):
        original_migrate(self)
        with self.connection:
            self.connection.execute("DELETE FROM experiment_exposures")
    python_break("migration loses exposure rows", "test_v15_migration_preserves_every_row",
                 (SQLiteStore, "_migrate"), destructive_migrate)
    original_delete = SQLiteStore.delete_all
    def consent_survives_delete(self, **kwargs):
        consent = self.connection.execute("SELECT * FROM learner_consent").fetchall()
        original_delete(self, **kwargs)
        with self.connection:
            self.connection.executemany("INSERT INTO learner_consent VALUES (?, ?, ?)", consent)
    python_break("deletion retains consent", "test_delete_restart_requires_consent_again",
                 (SQLiteStore, "delete_all"), consent_survives_delete)
    original_restart = SQLiteStore.restart_learner
    def automatic_reconsent(self):
        from datetime import datetime, timezone
        original_restart(self)
        self.confirm_consent(datetime.now(timezone.utc))
    python_break("restart skips new consent", "test_delete_restart_requires_consent_again",
                 (SQLiteStore, "restart_learner"), automatic_reconsent)
    node = ["node", "--test", "tests/foreman_web_contract.test.mjs", "tests/personal_comparison_web.test.mjs"]
    for label, old, new in [
        ("consent privacy statement missing", "not sent to any outside service, including AI models", "sent elsewhere"),
        ("consent contains mastery wording", "<h2>Before you start</h2>", "<h2>Before mastery</h2>"),
        ("consent has prechecked input", '<div class="empty consent">', '<div class="empty consent"><input type="checkbox" checked>'),
        ("workspace renders before consent", "if (view.consentRequired) return consentMarkup();", "if (false) return consentMarkup();"),
        ("boot ignores consent", "if (data.consentRequired) { renderConsent(); return; }", "if (false) { renderConsent(); return; }")]:
        source_break(label, "foreman_web/app.js", old, new, node)
    browser = ["npx.cmd" if os.name == "nt" else "npx", "playwright", "test", "--grep", "fresh consent gate", "--timeout=8000"]
    source_break("browser boot bypass", "foreman_web/app.js",
                 "if (data.consentRequired) { renderConsent(); return; }", "if (false) { renderConsent(); return; }",
                 browser, ROOT / "tests/browser")
    source_break("browser server gate bypass", "src/aesop_lab/storage/sqlite.py",
                 "if not self.has_consent():", "if False:", browser, ROOT / "tests/browser")
    print("All 14 deliberate breaks were detected; original source bytes restored.", flush=True)


if __name__ == "__main__":
    main()

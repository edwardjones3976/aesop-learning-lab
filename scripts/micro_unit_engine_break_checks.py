"""Run one isolated deliberate mutation per engine contract test, without editing sources.

Run with PYTHONPATH=src python scripts/micro_unit_engine_break_checks.py.
A detected mutation means an assertion failure, not an import/runtime error.
"""
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
import test_micro_unit_engine as tests
import test_micro_unit_content as content_tests
import aesop_lab.content.micro_unit as content
import aesop_lab.micro.engine as engine
import aesop_lab.storage.sqlite as storage

CASES = [
    ("daily_cap", engine, "self.daily_limit = daily_limit", "self.daily_limit = 99"),
    ("window_and_due_priority", engine, ">= timedelta(days=7)", ">= timedelta(days=6)"),
    ("stable_exposure_restart", storage, "SET {column} = COALESCE({column}, ?)", "SET {column} = ?"),
    ("first_answer", storage, "INSERT OR IGNORE INTO micro_check_attempts", "INSERT OR REPLACE INTO micro_check_attempts"),
    ("seed_and_warmup", engine, "if least < 2:", "if least < 0:"),
    ("policy_uses_received_feedback", engine, "if rng.random() < .2:", "if rng.random() < .8:"),
    ("eligible_only", engine, 'if classification == "eligible":', 'if classification in ("eligible", "early", "late", "assisted"):'),
    ("consent", storage, '        self.require_active_learner()\n', '        pass  # deliberately remove the write gate\n'),
    ("delete_export", storage, '            self.connection.execute("DELETE FROM micro_check_attempts")\n            self.connection.execute("DELETE FROM micro_exposures")', '            pass  # deliberately retain micro rows'),
    ("v16_migration", storage, 'self.connection.execute("PRAGMA user_version = 18")', 'self.connection.execute("PRAGMA user_version = 16")'),
    ("completed_replay", engine, '            if unit.id in exposures and exposures[unit.id]["completed_at"]:', '            if False:'),
    ("completed_replay", engine, 'or exposure.get("reexposed_at")', 'or False'),
    ("assignment_provenance", engine, 'provenance=provenance', 'provenance=None'),
    ("block_warmup", engine, 'self.units[uid].block == unit.block', 'True'),
    ("order_and_block_balance", engine, 'random.Random(self._seed("unit-order")).shuffle(units)', 'pass'),
    ("contamination", engine, 'check.get("outside_study") == "some"', 'False'),
    ("contamination", engine, 'check.get("previously_seen")', 'False'),
    ("v17_migration_preserves_rows", storage, 'self.connection.execute("PRAGMA user_version = 18")', 'self.connection.execute("PRAGMA user_version = 17")'),
    ("optional_block", content, 'self.text(u["block"], p + ".block") if "block" in u else None', 'None'),
    ("synthetic_60_days", engine, '"correct" if match else "incorrect"', '"incorrect" if match else "correct"'),
]


def main():
    detected = 0
    for name, module, before, after in CASES:
        source = Path(module.__file__).read_text()
        assert before in source, name
        namespace = {"__name__": module.__name__}
        exec(compile(source.replace(before, after), module.__file__, "exec"), namespace)
        symbol = ("MicroUnitEngine" if module is engine else
                  "parse_micro_unit_pack" if module is content else "SQLiteStore")
        test_module = content_tests if module is content else tests
        test_class = content_tests.MicroUnitPackTests if module is content else tests.MicroEngineTests
        output = io.StringIO()
        with patch.object(test_module, symbol, namespace[symbol]):
            result = unittest.TextTestRunner(stream=output).run(
                test_class("test_" + name))
        killed = bool(result.failures) and not result.errors
        detected += killed
        print(f"{name}: {'DETECTED (assertion failed)' if killed else 'NOT DETECTED AS EXPECTED'}")
        if not killed:
            print(output.getvalue())
    print(f"{detected}/{len(CASES)} deliberate breaks detected")
    return 0 if detected == len(CASES) else 1


if __name__ == "__main__":
    raise SystemExit(main())

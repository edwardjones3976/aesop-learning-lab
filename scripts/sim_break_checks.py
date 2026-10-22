"""Planted bugs for the round-2 simulator (decision section 2): each must make tests.test_sim_core fail.

Run from the repo root: py scripts/sim_break_checks.py. Every file is restored byte for byte.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "src/aesop_lab/sim"
MUTATIONS = [
    ("leaked future outcome", SIM / "fastpath.py",
     "if answer is None or answer.at > cutoff:", "if answer is None:"),
    ("day-1 check counted as delayed", SIM / "fastpath.py",
     "WINDOW_OPEN, WINDOW_CLOSE = timedelta(days=7)", "WINDOW_OPEN, WINDOW_CLOSE = timedelta(days=1)"),
    ("swapped answer key", SIM / "fastpath.py",
     "counts[unit.role][not answer.correct] += 1", "counts[unit.role][answer.correct] += 1"),
    ("declared outside study ignored", SIM / "fastpath.py",
     'if answer.outside_study == "some":', "if False:"),
    ("broken block balance", SIM / "learner.py",
     "roles.extend(protocol.block_roles(protocol.block_seed(identity, PACK_ID, ORDER_V1.contrast_id, block)))",
     "roles.extend([BASELINE, BASELINE, BASELINE, VARIANT])"),
    ("wrong call judged by the population sign", SIM / "run.py",
     "better = protocol.VARIANT if true_gap > 0 else protocol.BASELINE", "better = protocol.VARIANT"),
]


def main() -> int:
    missed = []
    for name, path, old, new in MUTATIONS:
        original = path.read_bytes()
        text = original.decode("utf-8")
        if text.count(old) != 1:
            print(f"SETUP ERROR: {name}: target text not found exactly once")
            return 2
        path.write_bytes(text.replace(old, new).encode("utf-8"))
        try:
            result = subprocess.run([sys.executable, "-m", "unittest", "tests.test_sim_core", "-q"],
                                    cwd=ROOT, capture_output=True, text=True,
                                    env={**os.environ, "PYTHONPATH": str(ROOT / "src")})
        finally:
            path.write_bytes(original)
        print(f"{'caught' if result.returncode else 'MISSED'}: {name}")
        if not result.returncode:
            missed.append(name)
    print(f"{len(MUTATIONS) - len(missed)}/{len(MUTATIONS)} planted bugs caught")
    return 1 if missed else 0


if __name__ == "__main__":
    raise SystemExit(main())

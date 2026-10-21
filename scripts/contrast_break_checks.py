"""Deliberate-break check for the contrast engine: run from the repo root; each mutation must fail tests.test_contrast_protocol."""
import subprocess
import sys
from pathlib import Path

root = Path.cwd()
proto = root / "src/aesop_lab/contrast/protocol.py"
engine = root / "src/aesop_lab/micro/engine.py"
mutations = [
    ("unbalanced blocks", proto, "for position in ranked[:2]:", "for position in ranked[:3]:"),
    ("no minimum count", proto, "if min(s + f for s, f in counts.values()) < MINIMUM_PER_ARM:", "if False:"),
    ("promising for both arms", proto, 'promising = _meets(p["variant_ahead"], PROMISING, p["error"])',
     'promising = max(p["variant_ahead"], 1 - p["variant_ahead"]) >= PROMISING'),
    ("late answers leak into a look", engine,
     'if not check or datetime.fromisoformat(check["occurred_at"]) > cutoff:', "if not check:"),
    ("block not stored before exposure", engine, "        if store:\n            row = self.store.store_contrast_block(",
     "        if False:\n            row = self.store.store_contrast_block("),
]
failed_to_break = []
for name, path, old, new in mutations:
    original = path.read_text(encoding="utf-8")
    assert original.count(old) == 1, name
    path.write_text(original.replace(old, new), encoding="utf-8", newline="\n")
    try:
        result = subprocess.run([sys.executable, "-m", "unittest", "tests.test_contrast_protocol", "-q"],
                                capture_output=True, text=True, env={**__import__("os").environ, "PYTHONPATH": "src"})
    finally:
        path.write_text(original, encoding="utf-8", newline="\n")
    caught = result.returncode != 0
    print(f"{'caught' if caught else 'MISSED'}: {name}")
    if not caught:
        failed_to_break.append(name)
sys.exit(1 if failed_to_break else 0)

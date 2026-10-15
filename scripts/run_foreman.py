"""Start the Foreman local preview without installing the package."""

from pathlib import Path
import argparse
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aesop_lab.foreman import DB, main


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the loopback-only Foreman preview")
    parser.add_argument("--port", type=int, default=8775)
    parser.add_argument("--db", type=Path, default=DB)
    options = parser.parse_args()
    main(port=options.port, db=options.db)

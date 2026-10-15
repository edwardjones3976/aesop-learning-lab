"""Start the Foreman local preview without installing the package."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aesop_lab.foreman import main


if __name__ == "__main__":
    main()

# ruff: noqa: E402

from pathlib import Path
import sys

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

from scripts.run_prta_gen_r41a_authorized_sequence import main


if __name__ == "__main__":
    raise SystemExit(main())

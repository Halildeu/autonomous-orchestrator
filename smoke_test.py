from __future__ import annotations

import runpy
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    runpy.run_path(str(repo_root / "ci" / "smoke_test.py"), run_name="__main__")


if __name__ == "__main__":
    main()

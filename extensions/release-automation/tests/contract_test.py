from __future__ import annotations

import runpy
from pathlib import Path


def main() -> None:
    target = Path(__file__).resolve().parents[2] / "PRJ-RELEASE-AUTOMATION" / "tests" / "contract_test.py"
    if not target.exists():
        raise SystemExit("extension_contract_test failed: canonical test file missing")
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()

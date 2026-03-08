from __future__ import annotations

import json
import sys

from src.ops.commands.enforcement_check import _ep002_legacy_manifest_overlay


def main() -> int:
    semgrep_payload = {
        "results": [
            {
                "check_id": "extensions.PRJ-ENFORCEMENT-PACK.semgrep.rules.enf.v1.ep002.structure_align",
                "path": "extensions/PRJ-GITHUB-OPS/extension.manifest.v1.json",
                "start": {"line": 49, "col": 1},
                "end": {"line": 49, "col": 32},
                "extra": {
                    "message": "false positive",
                    "severity": "WARNING",
                    "metadata": {"ep_id": "EP-002"},
                },
            },
            {
                "check_id": "extensions.PRJ-ENFORCEMENT-PACK.semgrep.rules.enf.v1.ep001.boundary_breach",
                "path": "src/prj_github_ops/smoke_fast_marker_extract.py",
                "start": {"line": 1, "col": 1},
                "end": {"line": 1, "col": 10},
                "extra": {
                    "message": "keep me",
                    "severity": "WARNING",
                    "metadata": {"ep_id": "EP-001"},
                },
            },
        ],
        "errors": [],
    }

    report_payload = _ep002_legacy_manifest_overlay(
        semgrep_payload,
        tracked_paths={"extensions/prj-github-ops/extension.manifest.v1.json"},
    )
    results = report_payload.get("results")
    if not isinstance(results, list) or len(results) != 2:
        raise SystemExit("enforcement_check_ep002_contract_test failed: unexpected results count")

    paths = {str(item.get("path")) for item in results if isinstance(item, dict)}
    if "extensions/PRJ-GITHUB-OPS/extension.manifest.v1.json" in paths:
        raise SystemExit("enforcement_check_ep002_contract_test failed: canonical path false positive retained")
    if "extensions/prj-github-ops/extension.manifest.v1.json" not in paths:
        raise SystemExit("enforcement_check_ep002_contract_test failed: legacy path finding not synthesized")
    if "src/prj_github_ops/smoke_fast_marker_extract.py" not in paths:
        raise SystemExit("enforcement_check_ep002_contract_test failed: unrelated finding dropped")

    print(json.dumps({"status": "OK", "results_count": len(results)}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

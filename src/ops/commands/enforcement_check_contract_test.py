from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator

from src.ops.commands.common import repo_root, warn


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("JSON_NOT_OBJECT")
    return obj


def _validate(schema: dict, instance: dict) -> list[str]:
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    return [e.message for e in validator.iter_errors(instance)]


def main() -> int:
    root = repo_root()
    ext = root / "extensions" / "PRJ-ENFORCEMENT-PACK"
    schema_path = ext / "contract" / "enforcement-check.schema.v1.json"
    matrix_path = ext / "contract" / "severity_matrix.v1.json"

    if not schema_path.exists():
        warn("FAIL error=MISSING_CONTRACT_SCHEMA")
        return 2
    if not matrix_path.exists():
        warn("FAIL error=MISSING_SEVERITY_MATRIX")
        return 2

    schema = _load_json(schema_path)
    matrix = _load_json(matrix_path)

    # Minimal synthetic semgrep payload (no semgrep binary required).
    semgrep_payload = {
        "results": [
            {
                "check_id": "enf.v1.ep001.boundary_breach",
                "path": "src/prj_github_ops/smoke_fast_marker_extract.py",
                "start": {"line": 1, "col": 1},
                "end": {"line": 1, "col": 10},
                "extra": {
                    "message": "Synthetic finding for contract validation.",
                    "severity": "WARNING",
                    "metadata": {"ep_id": "EP-001"},
                },
            }
        ],
        "errors": [],
    }

    from src.ops.commands.enforcement_check import _build_contract_report, _load_severity_matrix

    out = []
    for profile_name, expected_status in [
        ("default_profile", "WARN"),
        ("strict_profile", "BLOCKED"),
    ]:
        m, err = _load_severity_matrix(root, matrix_path, profile_name)
        if err:
            warn(f"FAIL error=INVALID_PROFILE profile={profile_name}")
            return 2

        report = _build_contract_report(
            root=root,
            intake_id="INTAKE-SYNTHETIC",
            rule_set_version="PRJ-ENFORCEMENT-PACK.semgrep_oss@0.1.0",
            profile_name=profile_name,
            matrix=m,
            semgrep_payload=semgrep_payload,
            semgrep_raw_rel=".cache/reports/semgrep_synth.json",
            delta_paths=["src/prj_github_ops/smoke_fast_marker_extract.py"],
            delta_paths_rel=".cache/reports/delta_paths_synth.txt",
            baseline_ref="HEAD~1",
            evidence_paths=["extensions/PRJ-ENFORCEMENT-PACK/contract/enforcement-check.schema.v1.json"],
            reasons=[],
        )

        report["generated_at"] = _now_iso_utc()
        report["run_id"] = f"ENFCHK-TEST-{profile_name}"

        errors = _validate(schema, report)
        if errors:
            warn(f"FAIL error=CONTRACT_SCHEMA_INVALID profile={profile_name} errors_count={len(errors)}")
            for e in errors[:5]:
                warn(f"  - {e}")
            return 2

        status = report.get("status")
        if status != expected_status:
            warn(f"FAIL error=STATUS_MISMATCH profile={profile_name} expected={expected_status} got={status}")
            return 2
        out.append({"profile": profile_name, "status": status})

    print(json.dumps({"status": "OK", "checks": out}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

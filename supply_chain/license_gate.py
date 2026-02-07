from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def fail(error_code: str, message: str, *, details: dict[str, Any] | None = None) -> int:
    payload: dict[str, Any] = {"status": "ERROR", "error_code": error_code, "message": message}
    if details:
        payload.update(details)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 1


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_str_list(v: Any) -> list[str]:
    if not isinstance(v, list):
        return []
    out: list[str] = []
    for x in v:
        if isinstance(x, str) and x.strip():
            out.append(x.strip())
    return out


def main() -> int:
    root = repo_root()
    policy_path = root / "policies" / "policy_license.v1.json"
    manifest_path = root / "supply_chain" / "dependency_licenses.v1.json"

    if not policy_path.exists():
        return fail("POLICY_MISSING", "Missing policies/policy_license.v1.json")
    if not manifest_path.exists():
        return fail("MANIFEST_MISSING", "Missing supply_chain/dependency_licenses.v1.json")

    try:
        policy = load_json(policy_path)
    except Exception as e:
        return fail("POLICY_INVALID", "Failed to parse policy JSON.", details={"error": str(e)})
    try:
        manifest = load_json(manifest_path)
    except Exception as e:
        return fail("MANIFEST_INVALID", "Failed to parse manifest JSON.", details={"error": str(e)})

    if not isinstance(policy, dict):
        return fail("POLICY_INVALID", "policy_license.v1.json must be a JSON object.")
    if not isinstance(manifest, dict):
        return fail("MANIFEST_INVALID", "dependency_licenses.v1.json must be a JSON object.")

    allowlist = set(normalize_str_list(policy.get("allowlist")))
    denylist = set(normalize_str_list(policy.get("denylist")))
    unknown_behavior = policy.get("unknown_behavior", "fail")
    unknown_behavior = unknown_behavior if isinstance(unknown_behavior, str) else "fail"
    unknown_behavior = unknown_behavior.strip().lower() if unknown_behavior else "fail"
    if unknown_behavior not in {"fail", "warn"}:
        unknown_behavior = "fail"

    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for dep_name in sorted(manifest.keys()):
        entry = manifest.get(dep_name)
        if not isinstance(dep_name, str) or not dep_name:
            continue
        if not isinstance(entry, dict):
            failures.append({"dependency": dep_name, "reason": "ENTRY_INVALID"})
            continue

        license_id = entry.get("license")
        license_id = license_id.strip() if isinstance(license_id, str) else ""

        if not license_id:
            item = {"dependency": dep_name, "reason": "LICENSE_MISSING"}
            if unknown_behavior == "warn":
                warnings.append(item)
            else:
                failures.append(item)
            continue

        if license_id in denylist:
            failures.append({"dependency": dep_name, "license": license_id, "reason": "DENYLISTED"})
            continue

        if allowlist and license_id not in allowlist:
            item = {"dependency": dep_name, "license": license_id, "reason": "NOT_ALLOWED"}
            if unknown_behavior == "warn":
                warnings.append(item)
            else:
                failures.append(item)

    status = "OK" if not failures else "ERROR"
    report = {
        "status": status,
        "dependency_count": len([k for k in manifest.keys() if isinstance(k, str) and k]),
        "failures": failures,
        "warnings": warnings,
        "unknown_behavior": unknown_behavior,
    }

    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if status == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())


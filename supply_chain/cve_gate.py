from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


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


def status_payload(
    *,
    status: str,
    checked_deps: list[str],
    unknown_deps: list[str],
    denied_hits: list[dict[str, str]],
    unknown_behavior: str,
) -> dict[str, Any]:
    return {
        "status": status,
        "checked_deps": checked_deps,
        "unknown_deps": unknown_deps,
        "denied_hits": denied_hits,
        "unknown_behavior": unknown_behavior,
    }


def main() -> int:
    root = repo_root()
    policy_path = root / "policies" / "policy_cve.v1.json"
    vulns_path = root / "supply_chain" / "dependency_vulns.v1.json"
    license_manifest_path = root / "supply_chain" / "dependency_licenses.v1.json"

    if not policy_path.exists():
        print(json.dumps({"status": "FAIL", "error": "POLICY_MISSING"}, sort_keys=True))
        return 1
    if not vulns_path.exists():
        print(json.dumps({"status": "FAIL", "error": "MANIFEST_MISSING"}, sort_keys=True))
        return 1
    if not license_manifest_path.exists():
        print(json.dumps({"status": "FAIL", "error": "LICENSE_MANIFEST_MISSING"}, sort_keys=True))
        return 1

    try:
        policy = load_json(policy_path)
    except Exception as e:
        print(json.dumps({"status": "FAIL", "error": "POLICY_INVALID", "message": str(e)}, sort_keys=True))
        return 1
    try:
        vulns = load_json(vulns_path)
    except Exception as e:
        print(json.dumps({"status": "FAIL", "error": "MANIFEST_INVALID", "message": str(e)}, sort_keys=True))
        return 1
    try:
        licenses = load_json(license_manifest_path)
    except Exception as e:
        print(json.dumps({"status": "FAIL", "error": "LICENSE_MANIFEST_INVALID", "message": str(e)}, sort_keys=True))
        return 1

    if not isinstance(policy, dict) or not isinstance(vulns, dict) or not isinstance(licenses, dict):
        print(json.dumps({"status": "FAIL", "error": "INPUTS_INVALID"}, sort_keys=True))
        return 1

    unknown_behavior = policy.get("unknown_behavior", "warn")
    unknown_behavior = unknown_behavior if isinstance(unknown_behavior, str) else "warn"
    unknown_behavior = unknown_behavior.strip().lower() if unknown_behavior else "warn"
    if unknown_behavior not in {"warn", "fail"}:
        unknown_behavior = "warn"

    deny_cves = set(normalize_str_list(policy.get("deny_cves")))

    checked_deps = sorted([k for k in licenses.keys() if isinstance(k, str) and k])
    unknown_deps: list[str] = []

    denied_pairs: set[tuple[str, str]] = set()

    for dep in checked_deps:
        entry = vulns.get(dep)
        if entry is None:
            unknown_deps.append(dep)
            continue
        if not isinstance(entry, dict):
            unknown_deps.append(dep)
            continue

        cves_raw = entry.get("cves", [])
        cves = normalize_str_list(cves_raw)
        for cve in cves:
            if cve in deny_cves:
                denied_pairs.add((dep, cve))

    unknown_deps = sorted(unknown_deps)
    denied_hits = [{"dependency": dep, "cve": cve} for dep, cve in sorted(denied_pairs)]

    if denied_hits:
        payload = status_payload(
            status="FAIL",
            checked_deps=checked_deps,
            unknown_deps=unknown_deps,
            denied_hits=denied_hits,
            unknown_behavior=unknown_behavior,
        )
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 1

    if unknown_deps:
        status = "WARN" if unknown_behavior == "warn" else "FAIL"
        payload = status_payload(
            status=status,
            checked_deps=checked_deps,
            unknown_deps=unknown_deps,
            denied_hits=denied_hits,
            unknown_behavior=unknown_behavior,
        )
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0 if status == "WARN" else 1

    payload = status_payload(
        status="OK",
        checked_deps=checked_deps,
        unknown_deps=[],
        denied_hits=[],
        unknown_behavior=unknown_behavior,
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())


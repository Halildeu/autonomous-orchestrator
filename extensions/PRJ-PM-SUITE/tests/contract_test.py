from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    manifest_path = Path(__file__).resolve().parents[1] / "extension.manifest.v1.json"
    if not manifest_path.exists():
        raise SystemExit("extension_contract_test failed: manifest missing")

    manifest = _load_json(manifest_path)
    schema_path = repo_root / "schemas" / "extension-manifest.schema.v1.json"
    Draft202012Validator(_load_json(schema_path)).validate(manifest)

    pm_policy_path = repo_root / "policies" / "policy_pm_suite.v1.json"
    pm_policy_schema_path = repo_root / "schemas" / "policy-pm-suite.schema.v1.json"
    pm_policy = _load_json(pm_policy_path)
    Draft202012Validator(_load_json(pm_policy_schema_path)).validate(pm_policy)
    if pm_policy.get("enabled") is not True:
        raise SystemExit("extension_contract_test failed: pm_suite policy must be enabled")
    execution_bridge = pm_policy.get("execution_bridge")
    if not isinstance(execution_bridge, dict) or execution_bridge.get("enabled") is not True:
        raise SystemExit("extension_contract_test failed: execution_bridge missing")

    delivery_session = pm_policy.get("delivery_session")
    if not isinstance(delivery_session, dict) or delivery_session.get("enabled") is not True:
        raise SystemExit("extension_contract_test failed: delivery_session missing")

    bridge_contract_path = repo_root / str(execution_bridge.get("contract_path") or "")
    bridge_schema_path = repo_root / str(execution_bridge.get("contract_schema_path") or "")
    bridge_checker_path = repo_root / str(execution_bridge.get("checker_path") or "")
    bridge_seed_path = repo_root / str(execution_bridge.get("seed_script_path") or "")
    for required_path in (bridge_contract_path, bridge_schema_path, bridge_checker_path, bridge_seed_path):
        if not required_path.exists():
            raise SystemExit(f"extension_contract_test failed: missing bridge path {required_path}")
    Draft202012Validator(_load_json(bridge_schema_path)).validate(_load_json(bridge_contract_path))

    session_builder_path = repo_root / str(delivery_session.get("builder_path") or "")
    session_guard_path = repo_root / str(delivery_session.get("guard_path") or "")
    session_packet_schema_path = repo_root / str(delivery_session.get("packet_schema_path") or "")
    for required_path in (session_builder_path, session_guard_path, session_packet_schema_path):
        if not required_path.exists():
            raise SystemExit(f"extension_contract_test failed: missing delivery session path {required_path}")

    docs_ref = manifest.get("docs_ref")
    if not isinstance(docs_ref, str) or not docs_ref:
        raise SystemExit("extension_contract_test failed: docs_ref missing")
    docs_path = docs_ref.split("#", 1)[0]
    if docs_path and not (repo_root / docs_path).exists():
        raise SystemExit("extension_contract_test failed: docs_ref path missing")

    ai_context_refs = manifest.get("ai_context_refs")
    if not isinstance(ai_context_refs, list) or not ai_context_refs:
        raise SystemExit("extension_contract_test failed: ai_context_refs missing")
    for ref in ai_context_refs:
        if not isinstance(ref, str) or not ref:
            raise SystemExit("extension_contract_test failed: ai_context_refs invalid")
        if not (repo_root / ref).exists():
            raise SystemExit("extension_contract_test failed: ai_context_refs path missing")

    from src.ops.extension_run import run_extension_run

    ws = repo_root / ".cache" / "ws_extension_contract"
    ws.mkdir(parents=True, exist_ok=True)

    extension_id = str(manifest.get("extension_id") or "").strip()
    res = run_extension_run(workspace_root=ws, extension_id=extension_id, mode="report", chat=False)
    if res.get("status") not in {"OK", "WARN", "IDLE"}:
        raise SystemExit("extension_contract_test failed: invalid status")
    if res.get("network_allowed") is not False:
        raise SystemExit("extension_contract_test failed: network must be disabled")

    contract_check_out = ws / ".cache" / "reports" / "feature_execution_contract_contract_test.v1.json"
    proc = subprocess.run(
        [
            "python3",
            str(bridge_checker_path),
            "--repo-root",
            str(repo_root),
            "--changed-files",
            "README.md",
            "--out",
            str(contract_check_out),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit("extension_contract_test failed: feature execution bridge checker must pass smoke run")

    session_packet_out = ws / ".cache" / "reports" / "delivery_session_packet_contract_test.v1.json"
    packet_proc = subprocess.run(
        [
            "python3",
            str(session_builder_path),
            "--repo-root",
            str(repo_root),
            "--out",
            str(session_packet_out),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if packet_proc.returncode != 0:
        raise SystemExit("extension_contract_test failed: delivery session builder must pass smoke run")
    Draft202012Validator(_load_json(session_packet_schema_path)).validate(_load_json(session_packet_out))

    session_guard_out = ws / ".cache" / "reports" / "delivery_session_guard_contract_test.v1.json"
    guard_proc = subprocess.run(
        [
            "python3",
            str(session_guard_path),
            "--repo-root",
            str(repo_root),
            "--packet",
            str(session_packet_out),
            "--changed-files",
            "README.md",
            "--out",
            str(session_guard_out),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if guard_proc.returncode != 0:
        raise SystemExit("extension_contract_test failed: delivery session guard must pass smoke run")

    print(json.dumps({"status": "OK", "extension_id": extension_id}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

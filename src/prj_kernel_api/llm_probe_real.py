"""Real probe: uses llm_live_probe to test providers, then updates probe state."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from src.prj_kernel_api.llm_live_probe import run_live_probe


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _resolve_workspace_root(repo_root: Path, workspace_root: str | Path | None) -> Path:
    if isinstance(workspace_root, Path):
        ws_root = workspace_root
    elif isinstance(workspace_root, str) and workspace_root.strip():
        ws_root = Path(workspace_root)
    else:
        ws_root = repo_root / ".cache" / "ws_customer_default"
    if not ws_root.is_absolute():
        ws_root = (repo_root / ws_root).resolve()
    return ws_root


def _policy_paths(repo_root: Path, workspace_root: str | Path | None = None):
    provider_map = repo_root / "docs" / "OPERATIONS" / "llm_provider_map.v1.json"
    ws_root = _resolve_workspace_root(repo_root, workspace_root)
    state_path = ws_root / ".cache" / "state" / "llm_probe_state.v1.json"
    return provider_map, state_path


def _results_by_provider(probe_report: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for item in probe_report.get("providers", []):
        if not isinstance(item, dict):
            continue
        pid = item.get("provider_id")
        if not isinstance(pid, str):
            continue
        out[pid] = item
    return out


def main(workspace_root: str | Path | None = None) -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    ws_root = _resolve_workspace_root(repo_root, workspace_root)
    workspace_root_str = str(ws_root)

    # 1) Run live probe (network). If disabled, this will skip with LIVE_DISABLED.
    status, _, report = run_live_probe(workspace_root=workspace_root_str, detail=False, env_mode="dotenv")

    # 2) Load provider map (SSOT) and current state (if any).
    provider_map_path, state_path = _policy_paths(repo_root, workspace_root=ws_root)
    provider_map = _load_json(provider_map_path)
    existing_state = state_path.exists() and _load_json(state_path) or {"state_version": "v0.1", "classes": {}}

    by_provider = _results_by_provider(report)
    now = datetime.now(timezone.utc).isoformat()

    # Start from existing state to avoid losing prior probe data.
    new_state: Dict[str, Any] = {
        "state_version": existing_state.get("state_version", "v0.1"),
        "generated_at": now,
        "classes": existing_state.get("classes", {}).copy(),
    }

    # 3) For each class/provider slot, update state based on live probe result.
    for cls_id, cls_data in provider_map.get("classes", {}).items():
        if not isinstance(cls_data, dict):
            continue
        provs = cls_data.get("providers", {}) if isinstance(cls_data, dict) else {}
        cls_state = new_state.setdefault("classes", {}).setdefault(cls_id, {"providers": {}})
        for prov_id, prov_data in provs.items():
            if not isinstance(prov_data, dict):
                continue
            pinned = prov_data.get("pinned_model_id")
            if not pinned:
                continue
            models = {m.get("model_id"): m for m in prov_data.get("models", []) if isinstance(m, dict)}
            if pinned not in models:
                continue
            probe_res = by_provider.get(prov_id)
            # If no probe result for this provider, keep previous state unchanged.
            if not probe_res:
                continue

            probe_status = "unknown"
            probe_error = None
            latency_ms = probe_res.get("elapsed_ms")
            if probe_res.get("status") == "OK":
                if probe_res.get("model") and probe_res.get("model") != pinned:
                    probe_status = "fail"
                    probe_error = "MODEL_MISMATCH"
                else:
                    probe_status = "ok"
            else:
                probe_status = "fail"
                probe_error = probe_res.get("error_code") or probe_res.get("error_type")

            prov_state = cls_state.setdefault("providers", {}).setdefault(prov_id, {"models": {}})
            existing_model_state = prov_state.get("models", {}).get(pinned, {})
            model_entry = models[pinned]
            verified_at = (
                existing_model_state.get("verified_at")
                if probe_status != "ok"
                else existing_model_state.get("verified_at") or model_entry.get("verified_at") or now
            )

            prov_state["models"][pinned] = {
                "probe_status": probe_status,
                "probe_last_at": now,
                "probe_latency_ms_p95": latency_ms,
                "probe_error_code": probe_error,
                "verified_at": verified_at,
                "probe_kind": "live_probe",
            }

    _write_json(state_path, new_state)
    print(f"Live probe status={status}, state updated at {state_path}")


if __name__ == "__main__":
    main()

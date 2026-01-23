"""Simple probe runner: marks pinned models as probe_ok in state (no network)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _policy_paths(repo_root: Path):
    provider_map = repo_root / "docs" / "OPERATIONS" / "llm_provider_map.v1.json"
    state_path = repo_root / ".cache" / "ws_customer_default" / ".cache" / "state" / "llm_probe_state.v1.json"
    return provider_map, state_path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    provider_map_path, state_path = _policy_paths(repo_root)
    provider_map = _load_json(provider_map_path)
    now = datetime.now(timezone.utc).isoformat()

    # Merge-only: never clobber existing state (semantic probes may have populated it).
    state: Dict[str, Any]
    if state_path.exists():
        try:
            state = _load_json(state_path)
        except Exception:
            state = {"state_version": "v0.1", "classes": {}}
    else:
        state = {"state_version": "v0.1", "classes": {}}

    if not isinstance(state, dict):
        state = {"state_version": "v0.1", "classes": {}}
    state.setdefault("state_version", "v0.1")
    state["generated_at"] = now
    if not isinstance(state.get("classes"), dict):
        state["classes"] = {}

    for cls_id, cls_data in provider_map.get("classes", {}).items():
        providers = cls_data.get("providers", {}) if isinstance(cls_data, dict) else {}
        st_providers: Dict[str, Any] = {}
        for prov_id, prov_data in providers.items():
            pinned = prov_data.get("pinned_model_id")
            if not pinned:
                continue
            models = prov_data.get("models", []) if isinstance(prov_data, dict) else []
            for m in models:
                if not isinstance(m, dict):
                    continue
                if m.get("model_id") != pinned:
                    continue
                st_providers.setdefault(prov_id, {"models": {}})
                existing_model_state = (
                    state.get("classes", {})
                    .get(cls_id, {})
                    .get("providers", {})
                    .get(prov_id, {})
                    .get("models", {})
                    .get(pinned, {})
                )
                if not isinstance(existing_model_state, dict):
                    existing_model_state = {}
                st_providers[prov_id]["models"][pinned] = {
                    "probe_status": "ok",
                    "probe_last_at": now,
                    "probe_latency_ms_p95": m.get("probe_latency_ms_p95"),
                    "probe_error_code": None,
                    "verified_at": existing_model_state.get("verified_at") or m.get("verified_at") or now,
                    "probe_kind": existing_model_state.get("probe_kind") or "synthetic_pinned_ok",
                }
        if st_providers:
            cls_state = state["classes"].setdefault(cls_id, {"providers": {}})
            if not isinstance(cls_state, dict):
                cls_state = {"providers": {}}
                state["classes"][cls_id] = cls_state
            cls_state.setdefault("providers", {})
            if not isinstance(cls_state.get("providers"), dict):
                cls_state["providers"] = {}
            for prov_id, prov_state in st_providers.items():
                dst_prov = cls_state["providers"].setdefault(prov_id, {"models": {}})
                if not isinstance(dst_prov, dict):
                    dst_prov = {"models": {}}
                    cls_state["providers"][prov_id] = dst_prov
                dst_prov.setdefault("models", {})
                if not isinstance(dst_prov.get("models"), dict):
                    dst_prov["models"] = {}
                dst_prov["models"].update(prov_state.get("models", {}))

    _write_json(state_path, state)
    print(f"Probe state written to {state_path}")


if __name__ == "__main__":
    main()

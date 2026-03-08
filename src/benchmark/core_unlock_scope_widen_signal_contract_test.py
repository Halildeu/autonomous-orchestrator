from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.benchmark.assessment_signals import _load_integration_coherence_signals

    ws = repo_root / ".cache" / "ws_core_unlock_scope_signal_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    # Stale compliance evidence alone must not raise scope widen.
    _write_json(
        ws / ".cache" / "reports" / "core_unlock_compliance.v1.json",
        {
            "version": "v1",
            "generated_at": "2026-03-01T00:00:00Z",
            "allowlist_used": ["src/ops/"],
            "changed_files": ["src/ops/example.py"],
        },
    )
    signals = _load_integration_coherence_signals(workspace_root=ws)
    if int(signals.get("core_unlock_scope_widen_count", -1)) != 0:
        raise SystemExit("core_unlock_scope_widen_signal_contract_test failed: stale report should not trigger widen")

    _write_json(
        ws / ".cache" / "policy_overrides" / "policy_core_immutability.override.v1.json",
        {
            "ssot_write_allowlist": ["AGENTS.md", "src/ops/"],
            "one_shot_src_window": {
                "enabled": False,
                "allow_paths": [],
                "ttl_seconds": 0,
                "opened_at": None,
                "expires_at": None,
                "reason": "",
                "restore_policy_hash": "",
            },
        },
    )
    signals = _load_integration_coherence_signals(workspace_root=ws)
    if int(signals.get("core_unlock_scope_widen_count", 0)) != 1:
        raise SystemExit("core_unlock_scope_widen_signal_contract_test failed: src allowlist must trigger widen")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

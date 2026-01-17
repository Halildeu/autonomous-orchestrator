from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.benchmark.assessment_runner import _load_intake_noise_signal

    ws = repo_root / ".cache" / "ws_operability_suppressed_unique_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    now_iso = _now_iso()
    old_iso = "2000-01-01T00:00:00Z"

    _write_json(
        ws / ".cache" / "index" / "intake_cooldowns.v1.json",
        {
            "version": "v1",
            "generated_at": now_iso,
            "workspace_root": str(ws),
            "entries": {
                "k1": {"last_seen": now_iso, "suppressed_count": 100},
                "k2": {"last_seen": now_iso, "suppressed_count": 5},
                "k3": {"last_seen": old_iso, "suppressed_count": 9999},
            },
        },
    )

    signal = _load_intake_noise_signal(workspace_root=ws)
    suppressed_24h = signal.get("suppressed_24h")
    if suppressed_24h != 2:
        raise SystemExit(
            "operability_suppressed_24h_unique_contract_test failed: "
            f"expected suppressed_24h=2 (unique keys), got {suppressed_24h}"
        )

    print(json.dumps({"status": "OK", "signal": signal}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()


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
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    from src.benchmark.eval_runner import run_eval

    ws_root = repo_root / ".cache" / "ws_customer_default" / ".cache" / "test_tmp" / "integrity_compat_findings"
    if ws_root.exists():
        shutil.rmtree(ws_root)

    _write_json(
        ws_root / ".cache" / "reports" / "integrity_verify.v1.json",
        {
            "verify_on_read_result": "PASS",
            "generated_at": _now_iso(),
        },
    )
    _write_json(
        ws_root / ".cache" / "index" / "assessment_raw.v1.json",
        {
            "version": "v1",
            "generated_at": _now_iso(),
            "workspace_root": str(ws_root),
            "integrity_snapshot_ref": ".cache/reports/integrity_verify.v1.json",
            "inputs": {"controls": 0, "metrics": 0},
            "signals": {"integrity": {"status": "PASS"}},
            "integration_coherence_signals": {},
        },
    )

    res = run_eval(workspace_root=ws_root, dry_run=False)
    _assert(res.get("status") in {"OK", "WARN", "SKIPPED"}, f"unexpected status: {res}")

    eval_path = ws_root / ".cache" / "index" / "assessment_eval.v1.json"
    _assert(eval_path.exists(), "assessment_eval.v1.json should be written")
    obj = json.loads(eval_path.read_text(encoding="utf-8"))

    lenses = obj.get("lenses") if isinstance(obj.get("lenses"), dict) else {}
    integrity = lenses.get("integrity_compat") if isinstance(lenses.get("integrity_compat"), dict) else {}
    findings = integrity.get("findings")
    _assert(isinstance(findings, dict), "integrity_compat.findings must be present")
    _assert(findings.get("version") == "v1", "integrity_compat.findings.version must be v1")
    items = findings.get("items")
    _assert(isinstance(items, list) and len(items) >= 2, "integrity_compat.findings.items must be non-empty")

    # Minimal shape checks (human-readable fields present).
    for it in items:
        _assert(isinstance(it, dict), "each findings item must be an object")
        _assert(isinstance(it.get("id"), str) and it["id"], "item.id required")
        _assert(isinstance(it.get("title"), str) and it["title"], "item.title required")
        _assert(isinstance(it.get("topic"), str) and it["topic"], "item.topic required")
        _assert(isinstance(it.get("match_status"), str) and it["match_status"], "item.match_status required")
        _assert(isinstance(it.get("summary"), str) and it["summary"], "item.summary required")
        _assert(isinstance(it.get("evidence_expectations"), list) and it["evidence_expectations"], "item.evidence_expectations required")
        _assert(isinstance(it.get("remediation"), list) and it["remediation"], "item.remediation required")

    print("OK")


if __name__ == "__main__":
    main()


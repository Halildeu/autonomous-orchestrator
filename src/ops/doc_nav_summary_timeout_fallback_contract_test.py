from __future__ import annotations

import argparse
import io
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

    from src.ops.commands.maintenance_doc_cmds import cmd_doc_nav_check

    ws = repo_root / ".cache" / "ws_doc_nav_summary_timeout_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    strict_report = {
        "version": "v1",
        "generated_at": _now_iso(),
        "repo_root": str(repo_root),
        "workspace_root": str(ws),
        "status": "OK",
        "counts": {
            "scanned_files": 1,
            "reference_count": 1,
            "broken_refs": 0,
            "orphan_critical": 0,
            "ambiguity": 0,
            "ambiguity_count": 0,
            "critical_nav_gaps": 0,
            "workspace_bound_refs_count": 0,
            "external_pointer_refs_count": 0,
            "placeholder_refs_count": 0,
            "archive_refs_count": 0,
        },
        "ref_summary": {
            "missing_file": 0,
            "wrong_path": 0,
            "deprecated": 0,
            "archive_ref": 0,
            "workspace_bound": 0,
            "external_pointer": 0,
            "plan_only_placeholder": 0,
        },
        "broken_refs": [],
        "top_placeholders": [],
        "orphan_critical": [],
        "ambiguities": [],
        "entrypoints": {},
        "notes": [],
    }
    strict_path = ws / ".cache" / "reports" / "doc_graph_report.strict.v1.json"
    _write_json(strict_path, strict_report)

    summary_path = ws / ".cache" / "reports" / "doc_graph_report.v1.json"
    if summary_path.exists():
        summary_path.unlink()

    buf = io.StringIO()
    args = argparse.Namespace(
        workspace_root=str(ws),
        detail="false",
        strict="false",
        chat="false",
    )
    sys_stdout = sys.stdout
    sys.stdout = buf
    try:
        rc = cmd_doc_nav_check(args)
    finally:
        sys.stdout = sys_stdout

    if rc != 0:
        raise SystemExit("doc_nav_summary_timeout_fallback_contract_test failed: non-zero rc")

    payloads = [line for line in buf.getvalue().splitlines() if line.strip().startswith("{")]
    if not payloads:
        raise SystemExit("doc_nav_summary_timeout_fallback_contract_test failed: missing JSON output")
    payload = json.loads(payloads[-1])

    if payload.get("error_code") != "SUMMARY_TIMEOUT_FALLBACK":
        raise SystemExit("doc_nav_summary_timeout_fallback_contract_test failed: missing error_code")
    notes = payload.get("notes") if isinstance(payload.get("notes"), list) else []
    if "summary_timeout_fallback_to_strict=true" not in notes:
        raise SystemExit("doc_nav_summary_timeout_fallback_contract_test failed: fallback note missing")
    if not summary_path.exists():
        raise SystemExit("doc_nav_summary_timeout_fallback_contract_test failed: summary report not written")


if __name__ == "__main__":
    main()

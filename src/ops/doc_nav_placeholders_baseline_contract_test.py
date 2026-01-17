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

    from src.ops.doc_graph import _load_policy, generate_doc_graph_report

    ws = repo_root / ".cache" / "ws_doc_nav_placeholders_baseline_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    sandbox_root = ws / "repo_root"
    (sandbox_root / "docs").mkdir(parents=True, exist_ok=True)
    (sandbox_root / "policies").mkdir(parents=True, exist_ok=True)
    (sandbox_root / "docs" / "ROADMAP.md").write_text(
        "Plan-only: formats/format-autopilot-chat.v1.json\n",
        encoding="utf-8",
    )
    _write_json(
        sandbox_root / "policies" / "policy_doc_graph.v1.json",
        {
            "version": "v1",
            "placeholders_baseline_enabled": True,
            "placeholders_warn_mode": "delta",
            "placeholders_warn_delta": 0,
        },
    )

    policy = _load_policy(sandbox_root, ws)
    report = generate_doc_graph_report(repo_root=sandbox_root, workspace_root=ws, policy=policy)
    counts = report.get("counts") if isinstance(report.get("counts"), dict) else {}
    placeholders_count = int(counts.get("placeholder_refs_count", 0))

    baseline_path = ws / ".cache" / "index" / "placeholders_baseline.v1.json"
    _write_json(
        baseline_path,
        {"version": "v1", "placeholders_baseline": placeholders_count, "captured_at": "fixed"},
    )

    report_same = generate_doc_graph_report(repo_root=sandbox_root, workspace_root=ws, policy=policy)
    if report_same.get("placeholders_baseline") != placeholders_count:
        raise SystemExit("doc_nav_placeholders_baseline_contract_test failed: baseline mismatch")
    if report_same.get("placeholders_delta") != 0:
        raise SystemExit("doc_nav_placeholders_baseline_contract_test failed: delta not zero")
    if report_same.get("placeholders_warn_mode") != "delta":
        raise SystemExit("doc_nav_placeholders_baseline_contract_test failed: warn_mode not delta")

    lowered = max(0, placeholders_count - 1)
    _write_json(
        baseline_path,
        {"version": "v1", "placeholders_baseline": lowered, "captured_at": "fixed"},
    )
    report_lower = generate_doc_graph_report(repo_root=sandbox_root, workspace_root=ws, policy=policy)
    if report_lower.get("placeholders_delta") != (placeholders_count - lowered):
        raise SystemExit("doc_nav_placeholders_baseline_contract_test failed: delta mismatch")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

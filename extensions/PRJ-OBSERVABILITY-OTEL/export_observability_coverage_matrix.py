from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


INVENTORY: list[dict[str, Any]] = [
    {
        "entrypoint_id": "runner_execute_finalize",
        "label": "Runner execute finalize stage",
        "path": "src/orchestrator/runner_stages/execute_finalize_stage.py",
        "trace_meta_expectation": "required",
        "ci_gate_refs": [
            "extensions/PRJ-OBSERVABILITY-OTEL/tests/contract_test.py",
        ],
    },
    {
        "entrypoint_id": "runner_quota_autonomy",
        "label": "Runner quota autonomy stage",
        "path": "src/orchestrator/runner_stages/quota_autonomy_stage.py",
        "trace_meta_expectation": "required",
        "ci_gate_refs": [],
    },
    {
        "entrypoint_id": "runner_routing_workflow",
        "label": "Runner routing workflow stage",
        "path": "src/orchestrator/runner_stages/routing_workflow_stage.py",
        "trace_meta_expectation": "required",
        "ci_gate_refs": [],
    },
    {
        "entrypoint_id": "github_ops_runtime",
        "label": "GitHub ops runtime",
        "path": "src/prj_github_ops/github_ops_runtime.py",
        "trace_meta_expectation": "required",
        "ci_gate_refs": [
            ".github/workflows/gate-enforcement-check.yml",
        ],
    },
    {
        "entrypoint_id": "cockpit_ops_server",
        "label": "Cockpit ops server utils",
        "path": "extensions/PRJ-UI-COCKPIT-LITE/server_utils_ops.py",
        "trace_meta_expectation": "required",
        "ci_gate_refs": [],
    },
    {
        "entrypoint_id": "ops_manage_cli",
        "label": "Ops manage CLI router",
        "path": "src/ops/manage.py",
        "trace_meta_expectation": "optional",
        "ci_gate_refs": [
            ".github/workflows/gate-enforcement-check.yml",
        ],
    },
]

TRACE_MARKERS = ("trace_meta", "attach_trace_meta(", "build_trace_meta(")
EVIDENCE_MARKERS = (".cache/reports", "evidence_paths", "out_dir=", "summary_path", "report_path")
OTEL_MARKERS = ("otel_bridge", "attach_trace_meta(")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    return parser.parse_args(argv)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _entry_status(*, expectation: str, trace_ok: bool, evidence_ok: bool) -> str:
    if expectation == "required" and (not trace_ok or not evidence_ok):
        return "WARN"
    return "OK"


def _render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Observability Coverage Matrix (v1)",
        "",
        f"status={payload['status']}",
        f"entrypoints_total={payload['totals']['entrypoints_total']}",
        f"required_entrypoints={payload['totals']['required_entrypoints']}",
        f"trace_hook_present={payload['totals']['trace_hook_present']}",
        f"evidence_signal_present={payload['totals']['evidence_signal_present']}",
        f"otel_bridge_present={payload['totals']['otel_bridge_present']}",
        f"ci_gate_present={payload['totals']['ci_gate_present']}",
        "",
        "| entrypoint | expectation | trace_meta | evidence | otel | ci_gate | status | path |",
        "|---|---|---:|---:|---:|---:|---|---|",
    ]
    for row in payload["entries"]:
        lines.append(
            f"| {row['entrypoint_id']} | {row['trace_meta_expectation']} | "
            f"{str(row['trace_meta_signal_present']).lower()} | "
            f"{str(row['evidence_signal_present']).lower()} | "
            f"{str(row['otel_bridge_signal_present']).lower()} | "
            f"{str(row['ci_gate_present']).lower()} | "
            f"{row['status']} | {row['path']} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = Path(args.repo_root).expanduser().resolve()
    entries: list[dict[str, Any]] = []
    totals = {
        "entrypoints_total": 0,
        "required_entrypoints": 0,
        "trace_hook_present": 0,
        "evidence_signal_present": 0,
        "otel_bridge_present": 0,
        "ci_gate_present": 0,
    }

    for item in INVENTORY:
        rel_path = str(item["path"])
        path = repo_root / rel_path
        text = _read_text(path)
        trace_ok = any(marker in text for marker in TRACE_MARKERS)
        evidence_ok = any(marker in text for marker in EVIDENCE_MARKERS)
        otel_ok = any(marker in text for marker in OTEL_MARKERS)
        ci_gate_refs = item.get("ci_gate_refs") if isinstance(item.get("ci_gate_refs"), list) else []
        ci_gate_ok = all((repo_root / str(ref)).exists() for ref in ci_gate_refs)
        expectation = str(item["trace_meta_expectation"])
        status = _entry_status(expectation=expectation, trace_ok=trace_ok, evidence_ok=evidence_ok)
        row = {
            "entrypoint_id": str(item["entrypoint_id"]),
            "label": str(item["label"]),
            "path": rel_path,
            "exists": path.exists(),
            "trace_meta_expectation": expectation,
            "trace_meta_signal_present": trace_ok,
            "evidence_signal_present": evidence_ok,
            "otel_bridge_signal_present": otel_ok,
            "ci_gate_present": ci_gate_ok,
            "ci_gate_refs": ci_gate_refs,
            "status": status,
        }
        entries.append(row)
        totals["entrypoints_total"] += 1
        if expectation == "required":
            totals["required_entrypoints"] += 1
        if trace_ok:
            totals["trace_hook_present"] += 1
        if evidence_ok:
            totals["evidence_signal_present"] += 1
        if otel_ok:
            totals["otel_bridge_present"] += 1
        if ci_gate_ok:
            totals["ci_gate_present"] += 1

    overall = "OK" if all(row["status"] == "OK" for row in entries) else "WARN"
    payload = {
        "version": "v1",
        "kind": "observability-coverage-matrix",
        "status": overall,
        "repo_root": repo_root.as_posix(),
        "entries": entries,
        "totals": totals,
    }
    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(_render_md(payload), encoding="utf-8")
    print(json.dumps({"status": "OK", "out_json": out_json.as_posix(), "out_md": out_md.as_posix()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

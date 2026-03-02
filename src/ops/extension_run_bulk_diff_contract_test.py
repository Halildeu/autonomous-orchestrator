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


def _must(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"extension_run_bulk_diff_contract_test failed: {message}")


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    import src.ops.extension_run_bulk_diff as mod

    ws = repo_root / ".cache" / "ws_extension_run_bulk_diff_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    original_discover = mod._discover_ops_single_gate_extensions
    original_build = mod.build_extension_run_report
    try:
        def _stub_discover(*, core_root: Path, extension_ids_filter: set[str] | None) -> list[dict]:
            base = [
                {
                    "extension_id": "PRJ-M0-MAINTAINABILITY",
                    "manifest_path": "extensions/PRJ-M0-MAINTAINABILITY/extension.manifest.v1.json",
                    "owner": "CORE",
                    "ops_single_gate": ["script-budget"],
                },
                {
                    "extension_id": "PRJ-GITHUB-OPS",
                    "manifest_path": "extensions/PRJ-GITHUB-OPS/extension.manifest.v1.json",
                    "owner": "CORE",
                    "ops_single_gate": ["github-ops-check"],
                },
            ]
            if isinstance(extension_ids_filter, set):
                return [item for item in base if item["extension_id"] in extension_ids_filter]
            return base

        def _stub_report(*, workspace_root: Path, extension_id: str, mode: str) -> dict:
            if extension_id == "PRJ-M0-MAINTAINABILITY":
                return {
                    "status": "WARN" if mode == "report" else "FAIL",
                    "selected_single_gate": "script-budget",
                    "single_gate_status": "FAIL",
                    "report_path": f".cache/reports/extension_run.{extension_id}.v1.json",
                    "error_code": "SINGLE_GATE_NOT_OK",
                    "single_gate_error_code": "",
                }
            return {
                "status": "OK" if mode == "report" else "WARN",
                "selected_single_gate": "github-ops-check",
                "single_gate_status": "WARN",
                "report_path": f".cache/reports/extension_run.{extension_id}.v1.json",
                "error_code": "",
                "single_gate_error_code": "",
            }

        mod._discover_ops_single_gate_extensions = _stub_discover
        mod.build_extension_run_report = _stub_report

        payload = mod.run_extension_run_bulk_diff(
            workspace_root=ws,
            extension_ids=None,
            emit_chg=True,
            chat=False,
        )
    finally:
        mod._discover_ops_single_gate_extensions = original_discover
        mod.build_extension_run_report = original_build

    _must(isinstance(payload, dict), "payload must be dict")
    _must(payload.get("status") == "WARN", "status should be WARN")
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    _must(summary.get("total_extensions") == 2, "total_extensions must be 2")
    _must(summary.get("mode_diff_count") == 2, "mode_diff_count must be 2")
    _must(summary.get("strict_attention_count") == 2, "strict_attention_count must be 2")

    closure_plan = payload.get("closure_plan") if isinstance(payload.get("closure_plan"), list) else []
    _must(len(closure_plan) == 2, "closure_plan size mismatch")
    first_plan = closure_plan[0] if closure_plan else {}
    _must(bool(first_plan.get("owner")), "closure owner missing")
    _must(bool(first_plan.get("eta")), "closure eta missing")

    chg_drafts = payload.get("chg_drafts") if isinstance(payload.get("chg_drafts"), list) else []
    _must(len(chg_drafts) == 2, "chg_drafts count must be 2")
    for draft in chg_drafts:
        plan_rel = str(draft.get("plan_path") or "")
        plan_md_rel = str(draft.get("plan_md_path") or "")
        _must(bool(plan_rel), "plan_path missing")
        _must(bool(plan_md_rel), "plan_md_path missing")
        _must((ws / plan_rel).exists(), f"plan file missing: {plan_rel}")
        _must((ws / plan_md_rel).exists(), f"plan md file missing: {plan_md_rel}")

    out_json = ws / ".cache" / "reports" / "extension_run_ops_single_gate_diff_matrix.v1.json"
    out_md = ws / ".cache" / "reports" / "extension_run_ops_single_gate_diff_matrix.v1.md"
    _must(out_json.exists(), "matrix json missing")
    _must(out_md.exists(), "matrix md missing")

    matrix_obj = json.loads(out_json.read_text(encoding="utf-8"))
    _must(matrix_obj.get("summary", {}).get("total_extensions") == 2, "matrix total mismatch")
    md_text = out_md.read_text(encoding="utf-8")
    _must("## Auto Closure Plan (mode_diff)" in md_text, "closure section missing in md")
    _must("## Auto CHG Drafts (strict WARN/FAIL)" in md_text, "chg section missing in md")

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

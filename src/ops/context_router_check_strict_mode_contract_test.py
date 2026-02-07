from __future__ import annotations

import argparse
import contextlib
import io
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


def _run_context_router_check(ctx_mod, ws: Path, mode: str) -> tuple[int, dict]:
    args = argparse.Namespace(
        workspace_root=str(ws),
        request_id="",
        text="",
        text_file="",
        in_json="",
        artifact_type="",
        domain="",
        kind="unspecified",
        impact_scope="workspace-only",
        requires_core_change=False,
        tenant_id="",
        source_type="human",
        source_channel="",
        source_user_id="",
        attachments_json="",
        constraints_json="",
        tags="",
        mode=mode,
        chat="false",
        detail="false",
        dry_run="true",
    )
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = ctx_mod.cmd_context_router_check(args)
    lines = [line.strip() for line in buf.getvalue().splitlines() if line.strip()]
    if not lines:
        raise SystemExit("context_router_check_strict_mode_contract_test failed: no output payload")
    try:
        payload = json.loads(lines[-1])
    except Exception as exc:
        raise SystemExit(f"context_router_check_strict_mode_contract_test failed: invalid JSON payload: {exc}")
    if not isinstance(payload, dict):
        raise SystemExit("context_router_check_strict_mode_contract_test failed: payload not object")
    return rc, payload


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    import src.ops.commands.context_cmds as ctx_mod
    import src.ops.context_pack_router as router_mod
    import src.ops.system_status_report as status_mod
    import src.ops.work_intake_from_sources as intake_mod

    ws = repo_root / ".cache" / "ws_context_router_check_strict_mode_contract"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    # Contract testin deterministic kalmasi icin agir operasyonlar stub'lanir.
    original_build = router_mod.build_context_pack
    original_route = router_mod.route_context_pack
    original_intake = intake_mod.run_work_intake_build
    original_status = status_mod.run_system_status
    observed_build_modes: list[str] = []

    def _stub_build_context_pack(*, workspace_root: Path, request_id: str | None, mode: str = "summary") -> dict:
        observed_build_modes.append(mode)
        pack_rel = Path(".cache") / "index" / "context_packs" / "CP-STUB.v1.json"
        pack_path = workspace_root / pack_rel
        _write_json(
            pack_path,
            {
                "version": "v1",
                "context_pack_id": "CP-STUB",
                "request_ref": {"request_id": request_id or "REQ-STUB"},
            },
        )
        return {
            "status": "OK",
            "request_id": request_id or "REQ-STUB",
            "context_pack_id": "CP-STUB",
            "context_pack_path": str(pack_rel),
            "summary_path": str(Path(".cache") / "reports" / "context_pack_summary.v1.md") if mode == "summary" else "",
        }

    def _stub_route_context_pack(*, workspace_root: Path, context_pack_path: Path | None = None) -> dict:
        payload = {
            "version": "v1",
            "status": "OK",
            "request_id": "REQ-STUB",
            "context_pack_id": "CP-STUB",
            "bucket": "PROJECT",
            "action": "PLAN",
            "severity": "S2",
            "priority": "P2",
            "next_actions": ["work-intake-check", "system-status", "context-pack-build"],
            "notes": ["PROGRAM_LED=true"],
        }
        _write_json(workspace_root / ".cache" / "reports" / "context_pack_router_result.v1.json", payload)
        return payload

    def _stub_run_work_intake_build(*, workspace_root: Path) -> dict:
        rel = Path(".cache") / "index" / "work_intake.v1.json"
        _write_json(
            workspace_root / rel,
            {
                "version": "v1",
                "plan_policy": "optional",
                "items": [],
                "summary": {"counts_by_bucket": {}},
            },
        )
        return {"status": "OK", "work_intake_path": str(rel)}

    def _stub_run_system_status(*, workspace_root: Path, core_root: Path, dry_run: bool) -> dict:
        out_json = workspace_root / ".cache" / "reports" / "system_status.v1.json"
        _write_json(
            out_json,
            {
                "generated_at": "2026-02-06T17:10:00Z",
                "overall_status": "OK",
                "sections": {},
            },
        )
        return {
            "status": "OK",
            "overall_status": "OK",
            "out_json": str(out_json),
            "out_md": str(workspace_root / ".cache" / "reports" / "system_status.v1.md"),
        }

    router_mod.build_context_pack = _stub_build_context_pack
    router_mod.route_context_pack = _stub_route_context_pack
    intake_mod.run_work_intake_build = _stub_run_work_intake_build
    status_mod.run_system_status = _stub_run_system_status
    try:
        rc_report, payload_report = _run_context_router_check(ctx_mod, ws, "report")
        if rc_report != 0:
            raise SystemExit("context_router_check_strict_mode_contract_test failed: report mode should return rc=0")
        if payload_report.get("status") != "OK":
            raise SystemExit("context_router_check_strict_mode_contract_test failed: report status should be OK")
        notes_report = payload_report.get("notes") if isinstance(payload_report.get("notes"), list) else []
        if "mode=report" not in notes_report:
            raise SystemExit("context_router_check_strict_mode_contract_test failed: mode=report note missing")

        rc_strict_missing, payload_strict_missing = _run_context_router_check(ctx_mod, ws, "strict")
        if rc_strict_missing == 0:
            raise SystemExit("context_router_check_strict_mode_contract_test failed: strict without doc_nav_strict should fail")
        if payload_strict_missing.get("status") != "FAIL":
            raise SystemExit("context_router_check_strict_mode_contract_test failed: strict missing should set status=FAIL")
        if payload_strict_missing.get("error_code") != "DOC_NAV_STRICT_MISSING":
            raise SystemExit("context_router_check_strict_mode_contract_test failed: strict missing error_code mismatch")

        _write_json(
            ws / ".cache" / "reports" / "doc_graph_report.strict.v1.json",
            {
                "version": "v1",
                "status": "OK",
                "doc_graph": {"critical_nav_gaps": 0},
            },
        )
        rc_strict_ok, payload_strict_ok = _run_context_router_check(ctx_mod, ws, "strict")
        if rc_strict_ok != 0:
            raise SystemExit("context_router_check_strict_mode_contract_test failed: strict with doc_nav_strict should pass")
        if payload_strict_ok.get("status") != "OK":
            raise SystemExit("context_router_check_strict_mode_contract_test failed: strict final status should be OK")
        notes_strict = payload_strict_ok.get("notes") if isinstance(payload_strict_ok.get("notes"), list) else []
        if "mode=strict" not in notes_strict:
            raise SystemExit("context_router_check_strict_mode_contract_test failed: mode=strict note missing")
        if "build_mode=detail" not in notes_strict:
            raise SystemExit("context_router_check_strict_mode_contract_test failed: build_mode=detail note missing")

        if observed_build_modes[:3] != ["summary", "detail", "detail"]:
            raise SystemExit(
                "context_router_check_strict_mode_contract_test failed: expected build modes summary/detail/detail"
            )
    finally:
        router_mod.build_context_pack = original_build
        router_mod.route_context_pack = original_route
        intake_mod.run_work_intake_build = original_intake
        status_mod.run_system_status = original_status

    print(json.dumps({"status": "OK"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

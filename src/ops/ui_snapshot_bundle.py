from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel_path(workspace_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _path_map(workspace_root: Path) -> dict[str, str]:
    return {
        "system_status": str(Path(".cache") / "reports" / "system_status.v1.json"),
        "portfolio_status": str(Path(".cache") / "reports" / "portfolio_status.v1.json"),
        "work_intake": str(Path(".cache") / "index" / "work_intake.v1.json"),
        "airunner_tick": str(Path(".cache") / "reports" / "airunner_tick.v1.json"),
        "airunner_deltas": str(Path(".cache") / "reports" / "airunner_deltas.v1.json"),
        "airunner_proof_bundle": str(Path(".cache") / "reports" / "airunner_proof_bundle.v1.json"),
        "jobs_index": str(Path(".cache") / "airunner" / "jobs_index.v1.json"),
        "extension_registry": str(Path(".cache") / "index" / "extension_registry.v1.json"),
        "decision_inbox": str(Path(".cache") / "index" / "decision_inbox.v1.json"),
        "release_plan": str(Path(".cache") / "reports" / "release_plan.v1.json"),
        "release_manifest": str(Path(".cache") / "reports" / "release_manifest.v1.json"),
        "release_apply_proof": str(Path(".cache") / "reports" / "release_apply_proof.v1.json"),
        "release_notes": str(Path(".cache") / "reports" / "release_notes.v1.md"),
        "github_ops_report": str(Path(".cache") / "reports" / "github_ops_report.v1.json"),
        "github_ops_jobs_index": str(Path(".cache") / "github_ops" / "jobs_index.v1.json"),
    }


def build_ui_snapshot_bundle(*, workspace_root: Path, out_path: Path | None = None) -> dict[str, Any]:
    paths = _path_map(workspace_root)
    non_json_keys = {"release_notes"}
    missing_paths: list[str] = []
    work_intake_total = 0
    work_intake_buckets: dict[str, int] = {}
    jobs_counts: dict[str, int] = {}
    extensions_total = 0
    release_status = ""
    decisions_total = 0
    decisions_by_kind: dict[str, int] = {}
    exec_ignored_count: int | None = None
    exec_skipped_count: int | None = None
    exec_decision_needed_count: int | None = None
    last_doer_actionability_path: str | None = None
    last_doer_exec_path: str | None = None
    last_doer_counts: dict[str, Any] | None = None
    last_auto_loop_path: str | None = None
    last_auto_loop_apply_details_path: str | None = None
    last_auto_loop_counts: dict[str, Any] | None = None
    doer_summary: dict[str, Any] | None = None
    doer_last_actionability_path: str | None = None
    doer_last_exec_report_path: str | None = None
    doer_last_run_path: str | None = None
    system_status_obj: dict[str, Any] | None = None

    for key, rel in paths.items():
        abs_path = workspace_root / rel
        if not abs_path.exists():
            missing_paths.append(rel)
            continue
        if key in non_json_keys:
            continue
        try:
            obj = _load_json(abs_path)
        except Exception:
            missing_paths.append(rel)
            continue
        if key == "system_status" and isinstance(obj, dict):
            system_status_obj = obj

        if key == "work_intake" and isinstance(obj, dict):
            items = obj.get("items") if isinstance(obj.get("items"), list) else []
            work_intake_total = len([i for i in items if isinstance(i, dict)])
            for item in items:
                if not isinstance(item, dict):
                    continue
                bucket = str(item.get("bucket") or "")
                if not bucket:
                    continue
                work_intake_buckets[bucket] = int(work_intake_buckets.get(bucket, 0)) + 1
        if key == "jobs_index" and isinstance(obj, dict):
            counts = obj.get("counts") if isinstance(obj.get("counts"), dict) else {}
            jobs_counts = {
                str(k): int(v) for k, v in counts.items() if isinstance(k, str) and isinstance(v, int) and v >= 0
            }
        if key == "extension_registry" and isinstance(obj, dict):
            if isinstance(obj.get("count_total"), int):
                extensions_total = int(obj.get("count_total") or 0)
            else:
                entries = obj.get("extensions") if isinstance(obj.get("extensions"), list) else []
                extensions_total = len([e for e in entries if isinstance(e, dict)])
        if key == "release_manifest" and isinstance(obj, dict):
            release_status = str(obj.get("status") or "")
        if key == "decision_inbox" and isinstance(obj, dict):
            counts = obj.get("counts") if isinstance(obj.get("counts"), dict) else {}
            decisions_total = int(counts.get("total") or 0) if isinstance(counts, dict) else 0
            by_kind = counts.get("by_kind") if isinstance(counts, dict) else {}
            if isinstance(by_kind, dict):
                decisions_by_kind = {
                    str(k): int(v) for k, v in by_kind.items() if isinstance(v, int) and v >= 0
                }

    summary = {
        "work_intake_total": work_intake_total,
        "work_intake_buckets": {k: work_intake_buckets[k] for k in sorted(work_intake_buckets)},
        "jobs_counts": {k: jobs_counts[k] for k in sorted(jobs_counts)},
        "extensions_total": extensions_total,
        "release_status": release_status,
        "missing_count": len(missing_paths),
        "decisions_total": decisions_total,
        "decisions_by_kind": {k: decisions_by_kind[k] for k in sorted(decisions_by_kind)},
    }
    last_decision_counts = {
        "total": decisions_total,
        "by_kind": {k: decisions_by_kind[k] for k in sorted(decisions_by_kind)},
    }

    status = "OK"
    if missing_paths:
        status = "WARN"
    if len(missing_paths) == len(paths):
        status = "IDLE"

    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "status": status,
        "paths": paths,
        "summary": summary,
        "missing_paths": sorted(missing_paths),
    }

    proof_path = workspace_root / ".cache" / "reports" / "airunner_proof_bundle.v1.json"
    if proof_path.exists():
        payload["last_airunner_proof_bundle_path"] = str(Path(".cache") / "reports" / proof_path.name)
    payload["last_decision_inbox_path"] = str(Path(".cache") / "index" / "decision_inbox.v1.json")
    payload["last_decision_counts"] = last_decision_counts
    payload["last_airunner_tick_path"] = paths.get("airunner_tick", "")
    if system_status_obj:
        sections = system_status_obj.get("sections") if isinstance(system_status_obj.get("sections"), dict) else {}
        doer_section = sections.get("doer") if isinstance(sections.get("doer"), dict) else {}
        if isinstance(doer_section.get("last_actionability_path"), str):
            doer_last_actionability_path = doer_section.get("last_actionability_path")
        if isinstance(doer_section.get("last_exec_report_path"), str):
            doer_last_exec_report_path = doer_section.get("last_exec_report_path")
        if isinstance(doer_section.get("last_run_path"), str):
            doer_last_run_path = doer_section.get("last_run_path")
        if isinstance(doer_section.get("last_counts"), dict):
            last_counts = doer_section.get("last_counts")
            if isinstance(last_counts.get("applied"), int):
                doer_summary = {
                    "applied": int(last_counts.get("applied") or 0),
                    "planned": int(last_counts.get("planned") or 0),
                    "skipped": int(last_counts.get("skipped") or 0),
                }

        doc_graph = sections.get("doc_graph") if isinstance(sections.get("doc_graph"), dict) else {}
        placeholders_count = doc_graph.get("placeholder_refs_count")
        placeholders_baseline = doc_graph.get("placeholders_baseline")
        placeholders_delta = doc_graph.get("placeholders_delta")
        if isinstance(placeholders_count, int):
            payload["doc_nav_placeholders_count"] = placeholders_count
        if isinstance(placeholders_baseline, int):
            payload["doc_nav_placeholders_baseline"] = placeholders_baseline
        if isinstance(placeholders_delta, int):
            payload["doc_nav_placeholders_delta"] = placeholders_delta
        airunner = sections.get("airunner") if isinstance(sections.get("airunner"), dict) else {}
        auto_mode = airunner.get("auto_mode") if isinstance(airunner.get("auto_mode"), dict) else None
        if isinstance(auto_mode, dict):
            payload["auto_mode_summary"] = auto_mode
        work_intake_exec = sections.get("work_intake_exec") if isinstance(sections.get("work_intake_exec"), dict) else {}
        if isinstance(work_intake_exec, dict):
            if isinstance(work_intake_exec.get("ignored_count"), int):
                exec_ignored_count = int(work_intake_exec.get("ignored_count") or 0)
            if isinstance(work_intake_exec.get("skipped_count"), int):
                exec_skipped_count = int(work_intake_exec.get("skipped_count") or 0)
            if isinstance(work_intake_exec.get("decision_needed_count"), int):
                exec_decision_needed_count = int(work_intake_exec.get("decision_needed_count") or 0)
            if last_doer_actionability_path is None and isinstance(
                work_intake_exec.get("last_doer_actionability_path"), str
            ):
                last_doer_actionability_path = work_intake_exec.get("last_doer_actionability_path")
            if last_doer_exec_path is None and isinstance(work_intake_exec.get("last_doer_exec_path"), str):
                last_doer_exec_path = work_intake_exec.get("last_doer_exec_path")
            if last_doer_counts is None and isinstance(work_intake_exec.get("last_doer_counts"), dict):
                last_doer_counts = work_intake_exec.get("last_doer_counts")
            if last_doer_counts is None and (last_doer_exec_path or exec_skipped_count is not None):
                skipped_by_reason = (
                    work_intake_exec.get("skipped_by_reason")
                    if isinstance(work_intake_exec.get("skipped_by_reason"), dict)
                    else {}
                )
                normalized_skipped = {
                    str(k): int(v)
                    for k, v in skipped_by_reason.items()
                    if isinstance(k, str) and isinstance(v, int) and v >= 0
                }
                skipped_val = int(work_intake_exec.get("skipped_count") or 0)
                if skipped_val > 0 and not normalized_skipped:
                    normalized_skipped = {"UNKNOWN": skipped_val}
                last_doer_counts = {
                    "applied": int(work_intake_exec.get("applied_count") or 0),
                    "planned": int(work_intake_exec.get("planned_count") or 0),
                    "skipped": skipped_val,
                    "skipped_by_reason": {k: normalized_skipped[k] for k in sorted(normalized_skipped)},
                }
        auto_loop = sections.get("auto_loop") if isinstance(sections.get("auto_loop"), dict) else {}
        if isinstance(auto_loop.get("last_auto_loop_path"), str):
            last_auto_loop_path = auto_loop.get("last_auto_loop_path")
        if isinstance(auto_loop.get("last_apply_details_path"), str):
            last_auto_loop_apply_details_path = auto_loop.get("last_apply_details_path")
        if isinstance(auto_loop.get("last_counts"), dict):
            counts = auto_loop.get("last_counts")
            applied_ids = counts.get("applied_intake_ids")
            planned_ids = counts.get("planned_intake_ids")
            limit_ids = counts.get("limit_reached_intake_ids")
            if not isinstance(applied_ids, list):
                applied_ids = []
            if not isinstance(planned_ids, list):
                planned_ids = []
            if not isinstance(limit_ids, list):
                limit_ids = []
            applied_ids = sorted({str(x) for x in applied_ids if isinstance(x, str) and x.strip()})
            planned_ids = sorted({str(x) for x in planned_ids if isinstance(x, str) and x.strip()})
            limit_ids = sorted({str(x) for x in limit_ids if isinstance(x, str) and x.strip()})
            last_auto_loop_counts = {
                "applied": int(counts.get("applied") or 0),
                "planned": int(counts.get("planned") or 0),
                "skipped": int(counts.get("skipped") or 0),
                "limit_reached": int(counts.get("limit_reached") or 0),
                "applied_intake_ids": applied_ids,
                "planned_intake_ids": planned_ids,
                "limit_reached_intake_ids": limit_ids,
            }
        if isinstance(exec_ignored_count, int):
            summary["work_intake_exec_ignored_count"] = exec_ignored_count
        if isinstance(exec_skipped_count, int):
            summary["work_intake_exec_skipped_count"] = exec_skipped_count
        if isinstance(exec_decision_needed_count, int):
            summary["work_intake_exec_decision_needed_count"] = exec_decision_needed_count

    if last_doer_actionability_path is None:
        actionability_path = workspace_root / ".cache" / "reports" / "doer_actionability.v1.json"
        if actionability_path.exists():
            last_doer_actionability_path = _rel_path(workspace_root, actionability_path)
    if last_doer_exec_path is None:
        exec_path = workspace_root / ".cache" / "reports" / "work_intake_exec_ticket.v1.json"
        if exec_path.exists():
            last_doer_exec_path = _rel_path(workspace_root, exec_path)
    if last_doer_counts is None and last_doer_exec_path:
        exec_path = workspace_root / last_doer_exec_path
        if exec_path.exists():
            try:
                exec_obj = _load_json(exec_path)
            except Exception:
                exec_obj = {}
            if isinstance(exec_obj, dict):
                skipped_by_reason = exec_obj.get("skipped_by_reason") if isinstance(exec_obj.get("skipped_by_reason"), dict) else {}
                normalized_skipped = {
                    str(k): int(v)
                    for k, v in skipped_by_reason.items()
                    if isinstance(k, str) and isinstance(v, int) and v >= 0
                }
                skipped_val = int(exec_obj.get("skipped_count") or 0)
                if skipped_val > 0 and not normalized_skipped:
                    normalized_skipped = {"UNKNOWN": skipped_val}
                last_doer_counts = {
                    "applied": int(exec_obj.get("applied_count") or 0),
                    "planned": int(exec_obj.get("planned_count") or 0),
                    "skipped": skipped_val,
                    "skipped_by_reason": {k: normalized_skipped[k] for k in sorted(normalized_skipped)},
                }
    if last_auto_loop_path is None:
        auto_loop_path = workspace_root / ".cache" / "reports" / "auto_loop.v1.json"
        if auto_loop_path.exists():
            last_auto_loop_path = _rel_path(workspace_root, auto_loop_path)
    if last_auto_loop_apply_details_path is None:
        apply_details_path = workspace_root / ".cache" / "reports" / "auto_loop_apply_details.v1.json"
        if apply_details_path.exists():
            last_auto_loop_apply_details_path = _rel_path(workspace_root, apply_details_path)
            if last_auto_loop_counts is None:
                try:
                    apply_obj = _load_json(apply_details_path)
                except Exception:
                    apply_obj = {}
                raw_counts = apply_obj.get("counts") if isinstance(apply_obj, dict) else {}
                if not isinstance(raw_counts, dict):
                    raw_counts = {}
                applied_ids = raw_counts.get("applied_intake_ids")
                planned_ids = raw_counts.get("planned_intake_ids")
                limit_ids = raw_counts.get("limit_reached_intake_ids")
                if not isinstance(applied_ids, list):
                    applied_ids = apply_obj.get("applied_intake_ids") if isinstance(apply_obj, dict) else []
                if not isinstance(planned_ids, list):
                    planned_ids = apply_obj.get("planned_intake_ids") if isinstance(apply_obj, dict) else []
                if not isinstance(limit_ids, list):
                    limit_ids = apply_obj.get("limit_reached_intake_ids") if isinstance(apply_obj, dict) else []
                applied_ids = sorted({str(x) for x in applied_ids if isinstance(x, str) and x.strip()})
                planned_ids = sorted({str(x) for x in planned_ids if isinstance(x, str) and x.strip()})
                limit_ids = sorted({str(x) for x in limit_ids if isinstance(x, str) and x.strip()})
                last_auto_loop_counts = {
                    "applied": int(raw_counts.get("applied") or len(applied_ids)),
                    "planned": int(raw_counts.get("planned") or len(planned_ids)),
                    "skipped": int(raw_counts.get("skipped") or 0),
                    "limit_reached": int(raw_counts.get("limit_reached") or len(limit_ids)),
                    "applied_intake_ids": applied_ids,
                    "planned_intake_ids": planned_ids,
                    "limit_reached_intake_ids": limit_ids,
                }
    if doer_summary is None and isinstance(last_doer_counts, dict):
        doer_summary = {
            "applied": int(last_doer_counts.get("applied") or 0),
            "planned": int(last_doer_counts.get("planned") or 0),
            "skipped": int(last_doer_counts.get("skipped") or 0),
        }
    if doer_last_actionability_path is None and isinstance(last_doer_actionability_path, str):
        doer_last_actionability_path = last_doer_actionability_path
    if doer_last_exec_report_path is None and isinstance(last_doer_exec_path, str):
        doer_last_exec_report_path = last_doer_exec_path
    if doer_last_run_path is None:
        run_path = workspace_root / ".cache" / "reports" / "airunner_run.v1.json"
        if run_path.exists():
            doer_last_run_path = _rel_path(workspace_root, run_path)
    if isinstance(last_doer_actionability_path, str):
        payload["last_doer_actionability_path"] = last_doer_actionability_path
    if isinstance(last_doer_exec_path, str):
        payload["last_doer_exec_path"] = last_doer_exec_path
    if isinstance(last_doer_counts, dict):
        payload["last_doer_counts"] = last_doer_counts
    if isinstance(last_auto_loop_path, str):
        payload["last_auto_loop_path"] = last_auto_loop_path
    if isinstance(last_auto_loop_apply_details_path, str):
        payload["last_auto_loop_apply_details_path"] = last_auto_loop_apply_details_path
    if isinstance(last_auto_loop_counts, dict):
        payload["last_auto_loop_counts"] = last_auto_loop_counts
    if isinstance(doer_summary, dict):
        payload["doer_summary"] = doer_summary
    if isinstance(doer_last_actionability_path, str):
        payload["doer_last_actionability_path"] = doer_last_actionability_path
    if isinstance(doer_last_exec_report_path, str):
        payload["doer_last_exec_report_path"] = doer_last_exec_report_path
    if isinstance(doer_last_run_path, str):
        payload["doer_last_run_path"] = doer_last_run_path

    out_path = out_path or (workspace_root / ".cache" / "reports" / "ui_snapshot_bundle.v1.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_dump_json(payload), encoding="utf-8")
    return payload


def run_ui_snapshot_bundle(*, workspace_root: Path, out: str | None = None) -> dict[str, Any]:
    out_path = None
    if out:
        out_path = Path(out)
        if not out_path.is_absolute():
            out_path = workspace_root / out_path
    payload = build_ui_snapshot_bundle(workspace_root=workspace_root, out_path=out_path)
    payload["report_path"] = _rel_path(workspace_root, (out_path or (workspace_root / ".cache" / "reports" / "ui_snapshot_bundle.v1.json")))
    return payload

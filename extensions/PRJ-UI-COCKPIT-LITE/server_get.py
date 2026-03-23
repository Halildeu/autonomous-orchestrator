from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from server_utils import *  # noqa: F403
from server_north_star import build_north_star_payload
from server_timeline import TIMELINE_SUMMARY_REL, derive_timeline_dashboard, run_timeline_watchdog


def _short_str(value: Any, limit: int = 300) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 3)]}..."


def _normalize_jsonable(obj: Any, depth: int = 0, max_depth: int = 6) -> Any:
    if depth > max_depth:
        return _short_str(obj)
    if isinstance(obj, dict):
        return {str(key): _normalize_jsonable(value, depth + 1, max_depth) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_normalize_jsonable(item, depth + 1, max_depth) for item in obj]
    if isinstance(obj, (tuple, set)):
        return [_normalize_jsonable(item, depth + 1, max_depth) for item in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, bytes):
        try:
            return obj.decode("utf-8")
        except Exception:
            return _short_str(obj)
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return _short_str(obj)


def _multi_repo_status_value(raw: Any, *, missing_to: str = "MISSING") -> str:
    raw_text = str(raw or "").strip().upper()
    if raw_text:
        return raw_text
    return missing_to


def _multi_repo_is_critical(raw: Any) -> bool:
    status = _multi_repo_status_value(raw)
    return status in {"FAIL", "BLOCKED", "NOT_READY", "WARN", "MISSING", "ERROR", "INVALID"}


def _multi_repo_status_weight(raw: Any) -> int:
    status = _multi_repo_status_value(raw)
    if status in {"FAIL", "BLOCKED", "NOT_READY", "MISSING", "ERROR", "INVALID"}:
        return 3
    if status in {"WARN", "IDLE", "UNKNOWN", "SKIPPED"}:
        return 1
    return 0


def _multi_repo_risk_level(score: int) -> str:
    if score >= 10:
        return "CRITICAL"
    if score >= 6:
        return "HIGH"
    if score >= 2:
        return "MEDIUM"
    return "LOW"


def _build_multi_repo_status_entry(raw_entry: dict[str, Any]) -> dict[str, Any]:
    workspace_root = str(raw_entry.get("workspace_root") or "").strip()
    workspace_path = Path(workspace_root).resolve() if workspace_root else None
    repo_root = str(raw_entry.get("repo_root") or "").strip()
    repo_id = str(raw_entry.get("repo_id") or "").strip() or (str(workspace_path.name) if workspace_path else "")
    repo_slug = str(raw_entry.get("repo_slug") or "").strip() or repo_id

    if workspace_path is None:
        return {
            "repo_id": repo_id,
            "repo_slug": repo_slug,
            "repo_root": repo_root,
            "workspace_root": workspace_root,
            "status_path": "",
            "status_exists": False,
            "status_json_valid": False,
            "overall_status": "MISSING",
            "extensions_single_gate_status": "MISSING",
            "extensions_registry_status": "MISSING",
            "extensions_isolation_status": "MISSING",
            "quality_gate_status": "MISSING",
            "readiness_status": "MISSING",
            "critical": True,
            "risk_score": 3,
            "risk_level": "MEDIUM",
            "gates": {
                "overall": "MISSING",
                "extensions": {
                    "single_gate_status": "MISSING",
                    "registry_status": "MISSING",
                    "isolation_status": "MISSING",
                },
                "quality_gate": "MISSING",
                "readiness": "MISSING",
            },
            "notes": ["workspace_root_missing"],
            "evidence": [],
        }

    status_path = workspace_path / ".cache" / "reports" / "system_status.v1.json"
    status_data, status_exists, status_json_valid = _read_json_file(status_path)
    status_data = status_data if isinstance(status_data, dict) else {}
    if not isinstance(status_data, dict):
        status_data = {}
    sections = status_data.get("sections") if isinstance(status_data, dict) else {}
    if not isinstance(sections, dict):
        sections = {}

    extensions = sections.get("extensions") if isinstance(sections, dict) else {}
    if not isinstance(extensions, dict):
        extensions = {}

    quality_gate = sections.get("quality_gate") if isinstance(sections, dict) else {}
    if not isinstance(quality_gate, dict):
        quality_gate = {}

    readiness = sections.get("readiness") if isinstance(sections, dict) else {}
    if not isinstance(readiness, dict):
        readiness = {}

    isolation = extensions.get("isolation_summary") if isinstance(extensions, dict) else {}
    if not isinstance(isolation, dict):
        isolation = {}

    overall_status = _multi_repo_status_value(status_data.get("overall_status") if status_exists else "MISSING")
    extensions_single_gate_status = _multi_repo_status_value(extensions.get("single_gate_status"))
    extensions_registry_status = _multi_repo_status_value(extensions.get("registry_status"))
    extensions_isolation_status = _multi_repo_status_value(isolation.get("status"))
    quality_gate_status = _multi_repo_status_value(quality_gate.get("status"))
    readiness_status = _multi_repo_status_value(readiness.get("status"))

    gate_scores = [
        overall_status,
        extensions_single_gate_status,
        extensions_registry_status,
        extensions_isolation_status,
        quality_gate_status,
        readiness_status,
    ]
    risk_score = sum(_multi_repo_status_weight(status) for status in gate_scores)
    notes = status_data.get("notes") if isinstance(status_data.get("notes"), list) else []
    if not status_exists:
        notes = ["system_status_missing", *[str(note) for note in notes]]
        if not notes:
            notes = ["system_status_missing"]
        risk_score += 3

    critical = any(_multi_repo_is_critical(value) for value in gate_scores)
    return {
        "repo_id": repo_id,
        "repo_slug": repo_slug,
        "repo_root": repo_root,
        "workspace_root": str(workspace_path),
        "status_path": str(status_path),
        "status_exists": bool(status_exists),
        "status_json_valid": bool(status_json_valid),
        "overall_status": overall_status,
        "extensions_single_gate_status": extensions_single_gate_status,
        "extensions_registry_status": extensions_registry_status,
        "extensions_isolation_status": extensions_isolation_status,
        "quality_gate_status": quality_gate_status,
        "readiness_status": readiness_status,
        "critical": bool(critical),
        "risk_score": int(risk_score),
        "risk_level": _multi_repo_risk_level(risk_score),
        "gates": {
            "overall": overall_status,
            "extensions": {
                "single_gate_status": extensions_single_gate_status,
                "registry_status": extensions_registry_status,
                "isolation_status": extensions_isolation_status,
            },
            "quality_gate": quality_gate_status,
            "readiness": readiness_status,
        },
        "notes": [str(note) for note in notes],
        "evidence": [str(status_path)],
    }


def _build_multi_repo_summary(entries: list[dict[str, Any]], *, critical_only: bool) -> dict[str, Any]:
    selected = [entry for entry in entries if not critical_only or bool(entry.get("critical"))]
    all_count = len(entries)
    selected_count = len(selected)

    def _norm_risk(value: Any) -> str:
        return str(value or "LOW").strip().upper()

    def _risk_bucket(level: str) -> str:
        n = _norm_risk(level)
        if n in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
            return n
        return "LOW"

    all_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    selected_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    all_risk_score = 0
    selected_risk_score = 0
    all_critical_count = 0
    selected_critical_count = 0

    for entry in entries:
        if bool(entry.get("critical")):
            all_critical_count += 1
        risk_level = _risk_bucket(entry.get("risk_level"))
        all_counts[risk_level] += 1
        try:
            all_risk_score += int(entry.get("risk_score") or 0)
        except Exception:
            all_risk_score += 0

    for entry in selected:
        if bool(entry.get("critical")):
            selected_critical_count += 1
        risk_level = _risk_bucket(entry.get("risk_level"))
        selected_counts[risk_level] += 1
        try:
            selected_risk_score += int(entry.get("risk_score") or 0)
        except Exception:
            selected_risk_score += 0

    selected_avg = round(selected_risk_score / selected_count, 2) if selected_count else 0.0

    return {
        "all_entries_count": all_count,
        "selected_entries_count": selected_count,
        "critical_only": bool(critical_only),
        "all_critical_count": all_critical_count,
        "selected_critical_count": selected_critical_count,
        "all_risk_score": all_risk_score,
        "selected_risk_score": selected_risk_score,
        "selected_risk_score_avg": selected_avg,
        "all_risk_level_counts": all_counts,
        "selected_risk_level_counts": selected_counts,
        "risk_line": (
            f"all={all_count} selected={selected_count} "
            f"critical={selected_critical_count}/{all_critical_count} "
            f"risk_score={selected_risk_score} risk_avg={selected_avg:.2f} "
            f"levels(Critical/High/Medium/Low)="
            f"{selected_counts['CRITICAL']}/{selected_counts['HIGH']}/"
            f"{selected_counts['MEDIUM']}/{selected_counts['LOW']}"
        ),
    }


def handle_do_get(self, *, repo_root: Path, ws_root: Path, allow_roots: list[Path], parsed) -> None:
    if parsed.path == "/":
        index_path = self.server.web_root / "index.html"
        self._serve_static(index_path, "text/html; charset=utf-8")
        return
    
    if parsed.path == "/assets/app.js":
        js_path = self.server.web_root / "assets" / "app.js"
        self._serve_static(js_path, "application/javascript; charset=utf-8")
        return
    
    if parsed.path == "/api/ws":
        sig = _mtime_sig(self.server.watch_paths)
        payload = {
            "workspace_root": str(ws_root),
            "last_modified_at": _last_modified(sig),
            "watch_paths": sorted(sig.keys()),
        }
        self._send_json(200, payload)
        return
    
    if parsed.path == "/api/health":
        self._send_json(200, {"status": "OK", "ts": int(time.time())})
        return

    if parsed.path == "/api/context-health":
        try:
            import subprocess, json as _cj
            result = subprocess.run(
                ["python3", "scripts/check_context_health.py", "--workspace-root", str(ws_root)],
                capture_output=True, text=True, timeout=10,
                cwd=str(Path(__file__).resolve().parents[2]),
            )
            if result.returncode == 0 and result.stdout.strip():
                data = _cj.loads(result.stdout.strip())
                data["ts"] = int(time.time())
                self._send_json(200, data)
            else:
                self._send_json(200, {"status": "ERROR", "score": 0, "grade": "F", "ts": int(time.time()), "error": result.stderr[:200] if result.stderr else "no output"})
        except Exception as exc:
            self._send_json(500, {"status": "ERROR", "error": str(exc)[:200]})
        return
    
    if parsed.path == "/api/search/index":
        qs = parse_qs(parsed.query)
        action = str(qs.get("action", ["status"])[0] or "status").strip().lower()
        engine = str(qs.get("engine", ["keyword"])[0] or "keyword").strip().lower()
        scope = str(qs.get("scope", ["ssot"])[0] or "ssot").strip().lower()
        rebuild = str(qs.get("rebuild", ["false"])[0] or "false").strip().lower() in {"1", "true", "yes", "on"}
        force = str(qs.get("force", ["false"])[0] or "false").strip().lower() in {"1", "true", "yes", "on"}
        max_files = qs.get("max_files", ["0"])[0]
        max_bytes = qs.get("max_bytes", ["6000000"])[0]
        chunk_size = qs.get("chunk_size", ["1200"])[0]
        max_file_bytes = qs.get("max_file_bytes", ["524288"])[0]
    
        mgr = getattr(self.server, "keyword_index", None)
        if mgr is None:
            self._send_json(500, {"status": "FAIL", "error": "SEARCH_INDEX_NOT_CONFIGURED"})
            return
    
        is_semantic = engine in {"semantic", "sem"}
        action_norm = action
        if action.startswith("semantic-"):
            is_semantic = True
            action_norm = action.split("semantic-", 1)[1].strip().lower() or "status"
    
        if is_semantic:
            if action_norm == "status":
                payload = mgr.semantic_index_status(scope=scope)
                self._send_json(200, payload)
                return
            if action_norm in {"build", "rebuild"}:
                payload = mgr.semantic_index_build(
                    scope=scope,
                    rebuild=(True if action_norm == "rebuild" else (rebuild or force)),
                    max_files=max_files,
                    max_bytes=max_bytes,
                    chunk_size=chunk_size,
                    max_file_bytes=max_file_bytes,
                )
                self._send_json(200, payload)
                return
            self._send_json(400, {"status": "FAIL", "error": "ACTION_INVALID"})
            return
    
        if action_norm == "status":
            payload = mgr.status(scope)
            self._send_json(200, payload)
            return
        if action_norm in {"build", "rebuild"}:
            payload = mgr.start_build(
                scope,
                force=(True if action_norm == "rebuild" else (rebuild or force)),
                max_files=max_files,
                max_file_bytes=max_file_bytes,
            )
            self._send_json(200, payload)
            return
    
        self._send_json(400, {"status": "FAIL", "error": "ACTION_INVALID"})
        return
    
    if parsed.path == "/api/search":
        qs = parse_qs(parsed.query)
        q = str(qs.get("q", [""])[0] or "").strip()
        scope = str(qs.get("scope", ["ssot"])[0] or "ssot").strip().lower()
        mode = str(qs.get("mode", ["auto"])[0] or "auto").strip().lower()
        pattern_mode = str(qs.get("pattern_mode", ["auto"])[0] or "auto").strip().lower()
        limit = qs.get("limit", ["80"])[0]
        auto_build = str(qs.get("auto_build", ["true"])[0] or "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
    
        mgr = getattr(self.server, "keyword_index", None)
        if mgr is None:
            self._send_json(500, {"status": "FAIL", "error": "SEARCH_INDEX_NOT_CONFIGURED"})
            return
    
        try:
            payload = mgr.search(
                q,
                scope=scope,
                search_mode=mode,
                pattern_mode=pattern_mode,
                limit=limit,
                auto_build=auto_build,
            )
            self._send_json(200, payload)
        except Exception as exc:
            self._send_json(
                500,
                {
                    "status": "FAIL",
                    "error": "SEARCH_RUNTIME_ERROR",
                    "detail": _short_str(exc, 500),
                    "query": q,
                    "scope": scope,
                    "mode": mode,
                },
            )
        return
    
    if parsed.path == "/api/search/capabilities":
        qs = parse_qs(parsed.query)
        scope = str(qs.get("scope", ["ssot"])[0] or "ssot").strip().lower()
        mgr = getattr(self.server, "keyword_index", None)
        if mgr is None:
            self._send_json(500, {"status": "FAIL", "error": "SEARCH_INDEX_NOT_CONFIGURED"})
            return
        try:
            payload = mgr.capabilities(scope=scope)
            self._send_json(200, payload)
        except Exception as exc:
            self._send_json(
                500,
                {
                    "status": "FAIL",
                    "error": "SEARCH_CAPABILITIES_RUNTIME_ERROR",
                    "detail": _short_str(exc, 500),
                    "scope": scope,
                },
            )
        return
    
    if parsed.path == "/api/op_job":
        qs = parse_qs(parsed.query)
        job_id = str(qs.get("job_id", [""])[0]).strip()
        if not job_id:
            self._send_json(400, {"status": "FAIL", "error": "JOB_ID_REQUIRED"})
            return
        if not isinstance(job_id, str) or not job_id.startswith("OPJOB-") or len(job_id) > 80:
            self._send_json(400, {"status": "FAIL", "error": "JOB_ID_INVALID"})
            return
        with self.server.op_jobs_lock:
            job = dict(self.server.op_jobs.get(job_id) or {})
        if not job:
            self._send_json(404, {"status": "FAIL", "error": "JOB_NOT_FOUND"})
            return
        result = job.get("result")
        if isinstance(result, dict):
            out = dict(result)
            out["job_id"] = job_id
            out["job_status"] = str(job.get("job_status") or "DONE")
            self._send_json(200, out)
            return
        self._send_json(
            200,
            {
                "status": str(job.get("job_status") or "PENDING"),
                "job_id": job_id,
                "job_status": str(job.get("job_status") or "PENDING"),
                "op": str(job.get("op") or ""),
                "trace_meta": job.get("trace_meta") if isinstance(job.get("trace_meta"), dict) else {},
                "created_at": str(job.get("created_at") or ""),
                "started_at": str(job.get("started_at") or ""),
            },
        )
        return
    
    if parsed.path == "/api/overview":
        status_path = ws_root / ".cache" / "reports" / "system_status.v1.json"
        snapshot_path = ws_root / ".cache" / "reports" / "ui_snapshot_bundle.v1.json"
        status_payload = self._wrap_file(status_path)
        snapshot_payload = self._wrap_file(snapshot_path)
        status_data = status_payload.get("data") if isinstance(status_payload, dict) else {}
        snapshot_data = snapshot_payload.get("data") if isinstance(snapshot_payload, dict) else {}
        sections = status_data.get("sections") if isinstance(status_data, dict) else {}
        work_intake = sections.get("work_intake") if isinstance(sections, dict) else {}
        decisions = sections.get("decisions") if isinstance(sections, dict) else {}
        auto_loop = sections.get("auto_loop") if isinstance(sections, dict) else {}
        doer = sections.get("doer") if isinstance(sections, dict) else {}
        doer_loop = sections.get("doer_loop") if isinstance(sections, dict) else {}
        summary = {
            "overall_status": status_data.get("overall_status") if isinstance(status_data, dict) else "",
            "work_intake_total": int(work_intake.get("items_count", 0) or 0) if isinstance(work_intake, dict) else 0,
            "work_intake_counts": work_intake.get("counts_by_bucket", {}) if isinstance(work_intake, dict) else {},
            "decision_pending": int(decisions.get("pending_decisions_count", 0) or 0) if isinstance(decisions, dict) else 0,
            "decision_seed_pending": int(decisions.get("seed_pending_count", 0) or 0)
            if isinstance(decisions, dict)
            else 0,
            "last_auto_loop_path": str(auto_loop.get("last_auto_loop_path") or "")
            if isinstance(auto_loop, dict)
            else "",
            "last_airrunner_run_path": str(doer.get("last_run_path") or "") if isinstance(doer, dict) else "",
            "last_exec_ticket_path": str(doer.get("last_exec_report_path") or "") if isinstance(doer, dict) else "",
            "lock_state": str(doer_loop.get("lock_state") or "") if isinstance(doer_loop, dict) else "",
        }
        payload = {
            "summary": summary,
            "system_status": status_payload,
            "ui_snapshot": snapshot_payload,
        }
        self._send_json(200, payload)
        return

    if parsed.path == "/api/multi-repo-status":
        qs = parse_qs(parsed.query)
        critical_only = _parse_bool_arg(qs.get("critical_only", ["false"])[0])
        print_evidence_map = _parse_bool_arg(qs.get("print_evidence_map", ["true"])[0])

        manifest = _read_managed_repos_manifest(ws_root)
        managed_entries = _collect_managed_repo_entries(ws_root)
        manifest_entries = [entry for entry in managed_entries if isinstance(entry, dict)]
        ws_root_key = str(ws_root.resolve())
        has_self = any(str(item.get("workspace_root") or "") == ws_root_key for item in manifest_entries)
        if not has_self:
            manifest_entries.append(
                {
                    "workspace_root": ws_root_key,
                    "repo_root": str(repo_root),
                    "repo_slug": "orchestrator-current",
                    "repo_id": "orchestrator-current",
                    "source": "self",
                }
            )

        raw_entries = [_build_multi_repo_status_entry(raw_entry) for raw_entry in manifest_entries]
        summary = _build_multi_repo_summary(raw_entries, critical_only=critical_only)
        entries = [
            entry
            for entry in raw_entries
            if (not summary["critical_only"] or bool(entry.get("critical")))
        ]
        if not print_evidence_map:
            for entry in entries:
                entry["evidence"] = []

        payload = {
            "status": "OK",
            "critical_only": bool(critical_only),
            "print_evidence_map": bool(print_evidence_map),
            "manifest_path": str(manifest.get("path", "")),
            "manifest_exists": bool(manifest.get("exists")),
            "manifest_json_valid": bool(manifest.get("json_valid")),
            "managed_workspace_root": ws_root_key,
            "summary": summary,
            "entries": entries,
        }
        self._send_json(200, payload)
        return

    if parsed.path == "/api/timeline":
        qs = parse_qs(parsed.query)
        run = _parse_bool_arg(qs.get("run", ["false"])[0])
        report_path = ws_root / TIMELINE_SUMMARY_REL
        run_result: dict[str, Any] | None = None
        if run or not report_path.exists():
            run_result = run_timeline_watchdog(repo_root, ws_root)
    
        report_data, exists, json_valid = _read_json_file(report_path)
        if not exists:
            self._send_json(
                404,
                {
                    "status": "FAIL",
                    "error": "TIMELINE_REPORT_NOT_FOUND",
                    "report_path": str(report_path),
                    "run": run_result or {},
                },
            )
            return
        if not json_valid:
            self._send_json(
                500,
                {
                    "status": "FAIL",
                    "error": "TIMELINE_REPORT_INVALID",
                    "report_path": str(report_path),
                    "run": run_result or {},
                },
            )
            return
    
        dashboard = derive_timeline_dashboard(report_data if isinstance(report_data, dict) else {})
        payload = {
            "status": "OK",
            "report_path": str(report_path),
            "run": run_result or {},
            "report": _redact(report_data),
            "dashboard": dashboard,
        }
        self._send_json(200, payload)
        return
    
    if parsed.path == "/api/north_star":
        payload = build_north_star_payload(
            repo_root=repo_root,
            ws_root=ws_root,
            wrap_file=self._wrap_file,
        )
        self._send_json(200, payload)
        return
    
    if parsed.path == "/api/status":
        path = ws_root / ".cache" / "reports" / "system_status.v1.json"
        self._send_json(200, self._wrap_file(path))
        return
    
    if parsed.path == "/api/ui_snapshot":
        path = ws_root / ".cache" / "reports" / "ui_snapshot_bundle.v1.json"
        self._send_json(200, self._wrap_file(path))
        return
    
    if parsed.path == "/api/inbox":
        path = ws_root / ".cache" / "index" / "input_inbox.v0.1.json"
        payload = self._wrap_file(path)
        data = payload.get("data") if isinstance(payload, dict) else {}
        items = data.get("items") if isinstance(data, dict) else []
        items_list = items if isinstance(items, list) else []
        payload["items"] = items_list[:200]
        self._send_json(200, payload)
        return
    
    if parsed.path == "/api/intake":
        path = ws_root / ".cache" / "index" / "work_intake.v1.json"
        payload = self._wrap_file(path)
        data = payload.get("data") if isinstance(payload, dict) else {}
        items = data.get("items") if isinstance(data, dict) else []
        items_list = items if isinstance(items, list) else []
        now = datetime.now(timezone.utc)
    
        claims_path = ws_root / ".cache" / "index" / "work_item_claims.v1.json"
        claims_payload: list[dict[str, Any]] = []
        if claims_path.exists():
            try:
                obj = json.loads(claims_path.read_text(encoding="utf-8"))
                if isinstance(obj, dict):
                    raw = obj.get("claims")
                    if isinstance(raw, list):
                        claims_payload = [c for c in raw if isinstance(c, dict)]
            except Exception:
                claims_payload = []
        active_claims: dict[str, dict[str, Any]] = {}
        for claim in claims_payload:
            work_item_id = str(claim.get("work_item_id") or "")
            if not work_item_id:
                continue
            exp = _parse_iso(str(claim.get("expires_at") or ""))
            if not exp or now >= exp:
                continue
            active_claims[work_item_id] = claim
    
        leases_path = ws_root / ".cache" / "index" / "work_item_leases.v1.json"
        leases_payload: list[dict[str, Any]] = []
        if leases_path.exists():
            try:
                obj = json.loads(leases_path.read_text(encoding="utf-8"))
                if isinstance(obj, dict):
                    raw = obj.get("leases")
                    if isinstance(raw, list):
                        leases_payload = [l for l in raw if isinstance(l, dict)]
            except Exception:
                leases_payload = []
        active_leases: dict[str, dict[str, Any]] = {}
        for lease in leases_payload:
            work_item_id = str(lease.get("work_item_id") or "")
            if not work_item_id:
                continue
            exp = _parse_iso(str(lease.get("expires_at") or ""))
            if not exp or now >= exp:
                continue
            active_leases[work_item_id] = lease
    
        enriched: list[dict[str, Any]] = []
        for item in items_list:
            if not isinstance(item, dict):
                continue
            intake_id = str(item.get("intake_id") or "")
            claim = active_claims.get(intake_id)
            lease = active_leases.get(intake_id)
            out_item = dict(item)
            if isinstance(claim, dict):
                out_item["claim_status"] = "CLAIMED"
                out_item["claim"] = {
                    "owner_tag": str(claim.get("owner_tag") or ""),
                    "owner_session": str(claim.get("owner_session") or ""),
                    "acquired_at": str(claim.get("acquired_at") or ""),
                    "expires_at": str(claim.get("expires_at") or ""),
                    "ttl_seconds": claim.get("ttl_seconds"),
                }
            else:
                out_item["claim_status"] = "FREE"
                out_item["claim"] = {}
            if isinstance(lease, dict):
                out_item["exec_lease_status"] = "LEASED"
                out_item["exec_lease"] = {
                    "owner": str(lease.get("owner") or ""),
                    "acquired_at": str(lease.get("acquired_at") or ""),
                    "expires_at": str(lease.get("expires_at") or ""),
                    "ttl_seconds": lease.get("ttl_seconds"),
                }
            else:
                out_item["exec_lease_status"] = "FREE"
                out_item["exec_lease"] = {}
            enriched.append(out_item)
        payload["summary"] = _summarize_intake(items_list)
        payload["claims_path"] = str(claims_path) if claims_path.exists() else ""
        payload["leases_path"] = str(leases_path) if leases_path.exists() else ""
        payload["items"] = enriched[:100]
        self._send_json(200, payload)
        return
    
    if parsed.path == "/api/decisions":
        path = ws_root / ".cache" / "index" / "decision_inbox.v1.json"
        payload = self._wrap_file(path)
        data = payload.get("data") if isinstance(payload, dict) else {}
        items = data.get("items") if isinstance(data, dict) else []
        items_list = items if isinstance(items, list) else []
        payload["summary"] = _summarize_decisions(items_list)
        payload["items"] = items_list[:100]
        self._send_json(200, payload)
        return
    
    if parsed.path == "/api/extensions":
        qs = parse_qs(parsed.query)
        extension_id = str(qs.get("extension_id", [""])[0]).strip()
        registry = _read_extension_registry(ws_root)
        overrides = _read_extension_overrides(ws_root)
        payload = {
            "registry_path": registry.get("path"),
            "registry_exists": registry.get("exists"),
            "registry_json_valid": registry.get("json_valid"),
            "items": _redact(registry.get("items") if isinstance(registry.get("items"), list) else []),
            "overrides": overrides,
        }
        if extension_id:
            if not EXTENSION_ID_RE.match(extension_id):
                self._send_json(400, {"status": "FAIL", "error": "EXTENSION_ID_INVALID"})
                return
            manifest_path = ""
            for entry in registry.get("items", []):
                if isinstance(entry, dict) and entry.get("extension_id") == extension_id:
                    manifest_path = str(entry.get("manifest_path") or "")
                    break
            manifest = _extension_manifest(repo_root, manifest_path)
            payload["extension_id"] = extension_id
            payload["manifest_path"] = manifest_path
            payload["manifest"] = _redact(manifest) if isinstance(manifest, dict) else {}
        self._send_json(200, payload)
        return
    
    if parsed.path == "/api/jobs":
        path = ws_root / ".cache" / "github_ops" / "jobs_index.v1.json"
        payload = self._wrap_file(path)
        data = payload.get("data") if isinstance(payload, dict) else {}
        items = data.get("jobs") if isinstance(data, dict) else []
        items_list = items if isinstance(items, list) else []
        payload["summary"] = _summarize_jobs(items_list)
        payload["jobs"] = items_list[:100]
        self._send_json(200, payload)
        return
    
    if parsed.path == "/api/airunner_jobs":
        path = ws_root / ".cache" / "airunner" / "jobs_index.v1.json"
        payload = self._wrap_file(path)
        data = payload.get("data") if isinstance(payload, dict) else {}
        items = data.get("jobs") if isinstance(data, dict) else []
        items_list = items if isinstance(items, list) else []
        payload["summary"] = _summarize_jobs(items_list)
        payload["jobs"] = items_list[:100]
        self._send_json(200, payload)
        return
    
    if parsed.path == "/api/locks":
        try:
            lock_path = ws_root / ".cache" / "doer" / "doer_loop_lock.v1.json"
            lock_data: dict[str, Any] = {}
            lock_state = "MISSING"
            owner_tag = ""
            owner_session = ""
            expires_at = ""
            run_id = ""
            if lock_path.exists():
                try:
                    lock_data = json.loads(lock_path.read_text(encoding="utf-8"))
                except Exception:
                    lock_state = "INVALID"
                else:
                    owner_tag = str(lock_data.get("owner_tag") or "")
                    owner_session = str(lock_data.get("owner_session") or "")
                    expires_at = str(lock_data.get("expires_at") or "")
                    run_id = str(lock_data.get("run_id") or "")
                    expires_dt = _parse_iso(expires_at)
                    now = datetime.now(timezone.utc)
                    lock_state = "LOCKED"
                    if expires_dt and now > expires_dt:
                        lock_state = "STALE"
            lease_summary = {
                "lease_count": 0,
                "active_count": 0,
                "owners_sample": [],
                "path": "",
            }
            leases_json = ws_root / ".cache" / "index" / "work_item_leases.v1.json"
            leases_jsonl = ws_root / ".cache" / "index" / "work_item_leases.v1.jsonl"
            leases_payload = []
            if leases_json.exists():
                try:
                    obj = json.loads(leases_json.read_text(encoding="utf-8"))
                    if isinstance(obj, dict):
                        leases_payload = obj.get("leases") if isinstance(obj.get("leases"), list) else []
                        lease_summary["path"] = str(leases_json)
                except Exception:
                    leases_payload = []
            elif leases_jsonl.exists():
                try:
                    lines = [line for line in leases_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
                    leases_payload = [json.loads(line) for line in lines if line.strip()]
                    lease_summary["path"] = str(leases_jsonl)
                except Exception:
                    leases_payload = []
            if isinstance(leases_payload, list) and leases_payload:
                lease_summary["lease_count"] = len(leases_payload)
                active = [l for l in leases_payload if isinstance(l, dict) and l.get("expires_at")]
                lease_summary["active_count"] = len(active)
                owners = sorted({str(l.get("owner") or "") for l in leases_payload if isinstance(l, dict)})
                lease_summary["owners_sample"] = [o for o in owners if o][:5]
    
            claim_summary = {"claim_count": 0, "active_count": 0, "owners_sample": [], "path": ""}
            active_claims_sample: list[dict[str, Any]] = []
            claims_json = ws_root / ".cache" / "index" / "work_item_claims.v1.json"
            claims_payload = []
            if claims_json.exists():
                try:
                    obj = json.loads(claims_json.read_text(encoding="utf-8"))
                    if isinstance(obj, dict):
                        claims_payload = obj.get("claims") if isinstance(obj.get("claims"), list) else []
                        claim_summary["path"] = str(claims_json)
                except Exception:
                    claims_payload = []
            if isinstance(claims_payload, list) and claims_payload:
                claim_summary["claim_count"] = len(claims_payload)
                now = datetime.now(timezone.utc)
                active = []
                for claim in claims_payload:
                    if not isinstance(claim, dict):
                        continue
                    claim_expires_dt = _parse_iso(str(claim.get("expires_at") or ""))
                    if not claim_expires_dt:
                        continue
                    if now >= claim_expires_dt:
                        continue
                    active.append(claim)
                claim_summary["active_count"] = len(active)
                owners = sorted({str(c.get("owner_tag") or "") for c in claims_payload if isinstance(c, dict)})
                claim_summary["owners_sample"] = [o for o in owners if o][:5]
                active_sorted = sorted(
                    active, key=lambda c: (str(c.get("expires_at") or ""), str(c.get("work_item_id") or ""))
                )
                for claim in active_sorted[:50]:
                    active_claims_sample.append(
                        {
                            "work_item_id": str(claim.get("work_item_id") or ""),
                            "owner_tag": str(claim.get("owner_tag") or ""),
                            "owner_session": str(claim.get("owner_session") or ""),
                            "acquired_at": str(claim.get("acquired_at") or ""),
                            "expires_at": str(claim.get("expires_at") or ""),
                            "ttl_seconds": claim.get("ttl_seconds"),
                        }
                    )
            payload = {
                "lock_state": lock_state,
                "lock_path": str(Path(".cache") / "doer" / "doer_loop_lock.v1.json"),
                "owner_tag": owner_tag,
                "owner_session": owner_session,
                "expires_at": expires_at,
                "run_id": run_id,
                "lock": _redact(lock_data) if lock_data else {},
                "leases_summary": lease_summary,
                "claims_summary": claim_summary,
                "claims_active_sample": active_claims_sample,
            }
            self._send_json(200, _normalize_jsonable(payload))
        except Exception as exc:
            self._send_json(
                500,
                {
                    "ok": False,
                    "error": "LOCKS_SERIALIZE_FAIL",
                    "detail": _short_str(exc),
                },
            )
        return
    
    if parsed.path == "/api/planner_chat/threads":
        threads = _list_planner_threads(ws_root)
        self._send_json(200, {"count": len(threads), "threads": threads})
        return
    
    if parsed.path == "/api/planner_chat":
        qs = parse_qs(parsed.query)
        thread_id = str(qs.get("thread", ["default"])[0]).strip().lower() or "default"
        if not _thread_id_valid(thread_id):
            self._send_json(400, {"status": "FAIL", "error": "THREAD_ID_INVALID"})
            return
        items = _list_planner_messages(ws_root, thread_id)
        self._send_json(200, {"thread_id": thread_id, "count": len(items), "items": _redact(items)})
        return
    
    if parsed.path == "/api/notes":
        items = _list_notes(ws_root)
        payload = {
            "notes_count": len(items),
            "items": _redact(items),
        }
        self._send_json(200, payload)
        return
    
    if parsed.path == "/api/notes/search":
        qs = parse_qs(parsed.query)
        term = str(qs.get("q", [""])[0]).strip().lower()
        items = _list_notes(ws_root)
        if term:
            filtered = []
            for item in items:
                title = str(item.get("title") or "").lower()
                body = str(item.get("body_excerpt") or "").lower()
                tags = " ".join([str(t) for t in item.get("tags", [])]).lower() if isinstance(item.get("tags"), list) else ""
                links = " ".join(
                    [f"{l.get('kind')}:{l.get('id_or_path')}" for l in item.get("links", []) if isinstance(l, dict)]
                ).lower() if isinstance(item.get("links"), list) else ""
                if term in title or term in body or term in tags or term in links:
                    filtered.append(item)
            items = filtered
        payload = {
            "notes_count": len(items),
            "items": _redact(items),
            "query": term,
        }
        self._send_json(200, payload)
        return
    
    if parsed.path == "/api/search":
        qs = parse_qs(parsed.query)
        term = str(qs.get("q", [""])[0]).strip()
        mode = str(qs.get("mode", [""])[0]).strip()
        scope = str(qs.get("scope", [""])[0]).strip()
        try:
            limit = int(str(qs.get("limit", ["20"])[0]))
        except Exception:
            limit = 20
        limit = max(1, min(limit, 200))
        rebuild = _parse_bool_arg(qs.get("rebuild", ["false"])[0])
        try:
            max_files = int(str(qs.get("max_files", [str(SEARCH_DEFAULT_MAX_FILES)])[0]))
        except Exception:
            max_files = SEARCH_DEFAULT_MAX_FILES
        try:
            max_bytes = int(str(qs.get("max_bytes", [str(SEARCH_DEFAULT_MAX_BYTES)])[0]))
        except Exception:
            max_bytes = SEARCH_DEFAULT_MAX_BYTES
        try:
            chunk_size = int(str(qs.get("chunk_size", [str(SEARCH_DEFAULT_CHUNK)])[0]))
        except Exception:
            chunk_size = SEARCH_DEFAULT_CHUNK
    
        payload = _search_router(
            repo_root=repo_root,
            ws_root=ws_root,
            query=term,
            mode_hint=mode,
            scope=scope,
            limit=limit,
            rebuild=rebuild,
            max_files=max(10, max_files),
            max_bytes=max(100000, max_bytes),
            chunk_size=max(200, chunk_size),
        )
        self._send_json(200, payload)
        return
    
    if parsed.path == "/api/search/index":
        qs = parse_qs(parsed.query)
        action = str(qs.get("action", ["status"])[0]).strip()
        scope = str(qs.get("scope", [""])[0]).strip()
        rebuild = _parse_bool_arg(qs.get("rebuild", ["false"])[0])
        try:
            max_files = int(str(qs.get("max_files", [str(SEARCH_DEFAULT_MAX_FILES)])[0]))
        except Exception:
            max_files = SEARCH_DEFAULT_MAX_FILES
        try:
            max_bytes = int(str(qs.get("max_bytes", [str(SEARCH_DEFAULT_MAX_BYTES)])[0]))
        except Exception:
            max_bytes = SEARCH_DEFAULT_MAX_BYTES
        try:
            chunk_size = int(str(qs.get("chunk_size", [str(SEARCH_DEFAULT_CHUNK)])[0]))
        except Exception:
            chunk_size = SEARCH_DEFAULT_CHUNK
    
        payload = _semantic_index_handle(
            repo_root=repo_root,
            ws_root=ws_root,
            scope=scope,
            action=action,
            rebuild=rebuild,
            max_files=max(10, max_files),
            max_bytes=max(100000, max_bytes),
            chunk_size=max(200, chunk_size),
        )
        self._send_json(200, payload)
        return
    
    if parsed.path == "/api/notes/get":
        qs = parse_qs(parsed.query)
        note_id = str(qs.get("note_id", [""])[0])
        if not _note_id_valid(note_id):
            self._send_json(400, {"status": "FAIL", "error": "NOTE_ID_INVALID"})
            return
        note_path = _notes_root(ws_root) / f"{note_id}.v1.json"
        payload = self._wrap_file(note_path)
        payload["note_id"] = note_id
        self._send_json(200, payload)
        return
    
    if parsed.path == "/api/chat":
        qs = parse_qs(parsed.query)
        try:
            limit = int(str(qs.get("limit", [str(CHAT_MAX_RETURN)])[0]))
        except Exception:
            limit = CHAT_MAX_RETURN
        limit = max(1, min(limit, CHAT_MAX_RETURN))
        items = _chat_read(ws_root, limit=limit)
        self._send_json(200, {"count": len(items), "items": _redact(items)})
        return
    
    if parsed.path == "/api/run_card":
        path = ws_root / ".cache" / "reports" / "RUN-CARD-LOCAL.v1.json"
        payload = self._wrap_file(path)
        payload["template_path"] = "docs/OPERATIONS/RUN-CARD-TEMPLATE.v1.md"
        self._send_json(200, payload)
        return
    
    if parsed.path == "/api/overrides/list":
        items = []
        for name in sorted(SAFE_OVERRIDE_FILES):
            path = _override_path(ws_root, name)
            exists = bool(path and path.exists())
            items.append(
                {
                    "name": name,
                    "path": str(path) if path else "",
                    "exists": exists,
                    "mtime": int(path.stat().st_mtime) if exists else None,
                    "size": int(path.stat().st_size) if exists else None,
                }
            )
        self._send_json(200, {"count": len(items), "items": items})
        return
    
    if parsed.path == "/api/overrides/get":
        qs = parse_qs(parsed.query)
        name = str(qs.get("name", [""])[0])
        if name not in SAFE_OVERRIDE_FILES:
            self._send_json(400, {"status": "FAIL", "error": "OVERRIDE_NOT_ALLOWED"})
            return
        path = _override_path(ws_root, name)
        if path is None:
            self._send_json(400, {"status": "FAIL", "error": "OVERRIDE_PATH_INVALID"})
            return
        payload = self._wrap_file(path)
        payload["name"] = name
        schema_path = _schema_path_for_override(repo_root, name)
        payload["schema_path"] = str(schema_path) if schema_path else ""
        if not payload.get("exists") and name == COCKPIT_LITE_OVERRIDE_NAME:
            payload["data"] = _cockpit_lite_override_template()
            payload["json_valid"] = True
        self._send_json(200, payload)
        return
    
    if parsed.path == "/api/settings/overrides":
        items = [item for item in _list_overrides(ws_root) if item.get("name") in SAFE_OVERRIDE_FILES]
        self._send_json(200, {"count": len(items), "items": items})
        return
    
    if parsed.path == "/api/settings/get":
        qs = parse_qs(parsed.query)
        name = str(qs.get("name", [""])[0])
        if name not in SAFE_OVERRIDE_FILES:
            self._send_json(400, {"status": "FAIL", "error": "OVERRIDE_NOT_ALLOWED"})
            return
        if not OVERRIDE_NAME_RE.match(name or ""):
            self._send_json(400, {"status": "FAIL", "error": "OVERRIDE_NAME_INVALID"})
            return
        path = _override_path(ws_root, name)
        if path is None or not path.exists():
            self._send_json(404, {"status": "FAIL", "error": "OVERRIDE_NOT_FOUND"})
            return
        payload = self._wrap_file(path)
        payload["name"] = name
        schema_path = _schema_path_for_override(repo_root, name)
        payload["schema_path"] = str(schema_path) if schema_path else ""
        self._send_json(200, payload)
        return
    
    if parsed.path == "/api/budget":
        path = repo_root / ".cache" / "script_budget" / "report.json"
        self._send_json(200, self._wrap_file(path))
        return
    
    if parsed.path == "/api/reports":
        qs = parse_qs(parsed.query)
        filter_value = str(qs.get("filter", ["closeout"])[0])
        reports_dir = ws_root / ".cache" / "reports"
        items = []
        if reports_dir.exists():
            for p in sorted(reports_dir.glob("*.json")):
                name = p.name
                if filter_value and filter_value not in name:
                    continue
                items.append({
                    "name": name,
                    "path": str(p),
                    "mtime": int(p.stat().st_mtime),
                    "size": int(p.stat().st_size),
                })
        self._send_json(200, {"items": items})
        return
    
    if parsed.path == "/api/evidence/list":
        qs = parse_qs(parsed.query)
        filter_value = str(qs.get("filter", ["closeout"])[0])
        evidence_root = ws_root / ".cache" / "reports"
        items = []
        if evidence_root.exists():
            for p in sorted(evidence_root.rglob("*")):
                if not p.is_file():
                    continue
                if p.suffix.lower() not in ALLOWED_EXTS:
                    continue
                rel = str(p.relative_to(evidence_root))
                if filter_value and filter_value not in rel:
                    continue
                items.append(
                    {
                        "name": p.name,
                        "path": str(p),
                        "relative_path": rel,
                        "mtime": int(p.stat().st_mtime),
                        "size": int(p.stat().st_size),
                    }
                )
        self._send_json(200, {"items": items})
        return
    
    if parsed.path == "/api/evidence/read":
        qs = parse_qs(parsed.query)
        raw_path = str(qs.get("path", [""])[0])
        path = _safe_resolve_path(raw_path, repo_root, ws_root, allow_roots)
        if path is None:
            self._send_json(400, {"status": "FAIL", "error": "PATH_NOT_ALLOWED"})
            return
        if ".cache/reports" not in str(path):
            self._send_json(400, {"status": "FAIL", "error": "PATH_NOT_ALLOWED"})
            return
        self._send_json(200, self._wrap_file(path))
        return
    
    if parsed.path == "/api/evidence/raw":
        qs = parse_qs(parsed.query)
        raw_path = str(qs.get("path", [""])[0])
        path = _safe_resolve_path(raw_path, repo_root, ws_root, allow_roots)
        if path is None:
            self._send_json(400, {"status": "FAIL", "error": "PATH_NOT_ALLOWED"})
            return
        if ".cache/reports" not in str(path):
            self._send_json(400, {"status": "FAIL", "error": "PATH_NOT_ALLOWED"})
            return
        if not path.exists():
            self._send_json(404, {"status": "FAIL", "error": "NOT_FOUND"})
            return
        content = path.read_text(encoding="utf-8")
        content_type = "text/plain; charset=utf-8"
        if path.suffix.lower() in {".json", ".jsonl"}:
            content_type = "application/json; charset=utf-8"
        elif path.suffix.lower() == ".md":
            content_type = "text/markdown; charset=utf-8"
        self._send_text(200, content, content_type)
        return
    
    if parsed.path == "/api/file":
        qs = parse_qs(parsed.query)
        raw_path = str(qs.get("path", [""])[0])
        path = _safe_resolve_path(raw_path, repo_root, ws_root, allow_roots)
        if path is None:
            self._send_json(400, {"status": "FAIL", "error": "PATH_NOT_ALLOWED"})
            return
        self._send_json(200, self._wrap_file(path))
        return
    
    if parsed.path == "/api/stream":
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
    
        last_sig = _mtime_sig(self.server.watch_paths)
        try:
            while True:
                time.sleep(self.server.poll_interval)
                sig = _mtime_sig(self.server.watch_paths)
                if sig != last_sig:
                    changed = [p for p, v in sig.items() if last_sig.get(p) != v]
                    payload = _json_dumps({"paths": sorted(changed), "ts": int(time.time())})
                    event_map = {
                        "overview_tick": any(
                        "system_status.v1.json" in p
                        or "ui_snapshot_bundle.v1.json" in p
                        or "codex_timeline_summary.v1.json" in p
                        for p in changed
                        ),
                        "inbox_tick": any(
                            "input_inbox.v0.1.json" in p or "manual_request_triage.v0.1.json" in p for p in changed
                        ),
                        "intake_tick": any("work_intake.v1.json" in p for p in changed),
                        "decisions_tick": any("decision_inbox.v1.json" in p for p in changed),
                        "jobs_tick": any("jobs_index.v1.json" in p for p in changed),
                        "locks_tick": any("doer_loop_lock.v1.json" in p for p in changed),
                        "notes_tick": any(".cache/notes/" in p for p in changed),
                        "chat_tick": any(
                            ".cache/notes/planner" in p or ".cache/chat_console" in p for p in changed
                        ),
                        "settings_tick": any(
                            ".cache/policy_overrides" in p
                            or "RUN-CARD-LOCAL.v1.json" in p
                            or ".cache/extension_overrides" in p
                            or ".cache/chat_console" in p
                            for p in changed
                        ),
                    }
                    for event_name in [
                        "overview_tick",
                        "inbox_tick",
                        "intake_tick",
                        "decisions_tick",
                        "jobs_tick",
                        "locks_tick",
                        "notes_tick",
                        "chat_tick",
                        "settings_tick",
                    ]:
                        if event_map.get(event_name):
                            self.wfile.write(f"event: {event_name}\n".encode("utf-8"))
                            self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                    self.wfile.write(b"event: changed\n")
                    self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    last_sig = sig
        except Exception:
            return
    
    self._send_json(404, {"status": "FAIL", "error": "NOT_FOUND"})

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from server_utils import *  # noqa: F403


def do_GET(self) -> None:  # noqa: N802
    repo_root = self.server.repo_root
    ws_root = self.server.workspace_root
    allow_roots = self.server.allow_roots
    parsed = urlparse(self.path)

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

    if parsed.path == "/api/north_star":
        eval_path = ws_root / ".cache" / "index" / "assessment_eval.v1.json"
        raw_path = ws_root / ".cache" / "index" / "assessment_raw.v1.json"
        gap_path = ws_root / ".cache" / "index" / "gap_register.v1.json"
        trend_catalog_path = ws_root / ".cache" / "index" / "trend_catalog.v1.json"
        bp_catalog_path = ws_root / ".cache" / "index" / "bp_catalog.v1.json"
        north_star_catalog_path = ws_root / ".cache" / "index" / "north_star_catalog.v1.json"
        scorecard_path = ws_root / ".cache" / "reports" / "benchmark_scorecard.v1.json"
        llm_live_readiness_path = ws_root / ".cache" / "reports" / "llm_live_readiness.v1.json"
        eval_payload = self._wrap_file(eval_path)
        raw_payload = self._wrap_file(raw_path)
        gap_payload = self._wrap_file(gap_path)
        trend_catalog_payload = self._wrap_file(trend_catalog_path)
        bp_catalog_payload = self._wrap_file(bp_catalog_path)
        north_star_catalog_payload = self._wrap_file(north_star_catalog_path)
        scorecard_payload = self._wrap_file(scorecard_path)
        llm_live_readiness_payload = self._wrap_file(llm_live_readiness_path)

        eval_data = eval_payload.get("data") if isinstance(eval_payload, dict) else {}
        raw_data = raw_payload.get("data") if isinstance(raw_payload, dict) else {}
        gap_data = gap_payload.get("data") if isinstance(gap_payload, dict) else {}
        lenses = eval_data.get("lenses") if isinstance(eval_data, dict) else {}
        gaps = gap_data.get("gaps") if isinstance(gap_data, dict) else []
        gap_list = gaps if isinstance(gaps, list) else []

        # Surface “capability vs expected” (monitoring) so UI can show:
        # enabled_effective / auto_mode_enabled_effective (capability)
        # heartbeat_expectation_mode (monitoring/expected)
        raw_signals = raw_data.get("signals") if isinstance(raw_data, dict) else {}
        airunner_state = (
            raw_signals.get("airunner_state") if isinstance(raw_signals.get("airunner_state"), dict) else {}
        )
        enabled_effective = (
            bool(airunner_state.get("enabled_effective"))
            if isinstance(airunner_state, dict) and "enabled_effective" in airunner_state
            else None
        )
        auto_mode_enabled_effective = (
            bool(airunner_state.get("auto_mode_enabled_effective"))
            if isinstance(airunner_state, dict) and "auto_mode_enabled_effective" in airunner_state
            else None
        )
        active_hours_is_now = None
        if isinstance(airunner_state, dict) and "active_hours_is_now" in airunner_state:
            active_hours_value = airunner_state.get("active_hours_is_now")
            active_hours_is_now = active_hours_value if isinstance(active_hours_value, bool) else None
        heartbeat_stale_seconds = None
        if isinstance(airunner_state, dict) and "heartbeat_stale_seconds" in airunner_state:
            try:
                heartbeat_stale_seconds = int(airunner_state.get("heartbeat_stale_seconds") or 0)
            except Exception:
                heartbeat_stale_seconds = None

        heartbeat_expectation_mode = None
        mode_source = "default"
        override_path = ws_root / ".cache" / "policy_overrides" / "policy_north_star_operability.override.v1.json"
        override_obj, override_exists, override_valid = _read_json_file(override_path)
        if override_exists and override_valid and isinstance(override_obj, dict):
            heartbeat_expectation_mode = override_obj.get("heartbeat_expectation_mode")
            if heartbeat_expectation_mode:
                mode_source = "override"
        policy_path = repo_root / "policies" / "policy_north_star_operability.v1.json"
        policy_obj, policy_exists, policy_valid = _read_json_file(policy_path)
        thresholds = (
            policy_obj.get("thresholds")
            if policy_exists and policy_valid and isinstance(policy_obj, dict) and isinstance(policy_obj.get("thresholds"), dict)
            else {}
        )
        override_thresholds = (
            override_obj.get("thresholds")
            if override_exists and override_valid and isinstance(override_obj, dict) and isinstance(override_obj.get("thresholds"), dict)
            else {}
        )
        if override_thresholds:
            merged = dict(thresholds)
            merged.update(override_thresholds)
            thresholds = merged

        if not heartbeat_expectation_mode and policy_exists and policy_valid and isinstance(policy_obj, dict):
            heartbeat_expectation_mode = policy_obj.get("heartbeat_expectation_mode")
        heartbeat_expectation_mode = str(heartbeat_expectation_mode or "ALWAYS").strip().upper()
        if heartbeat_expectation_mode not in {"ALWAYS", "ACTIVE_HOURS", "NONE"}:
            heartbeat_expectation_mode = "ALWAYS"

        heartbeat_warn_seconds = None
        heartbeat_fail_seconds = None
        if isinstance(thresholds, dict):
            try:
                heartbeat_warn_seconds = int(thresholds.get("heartbeat_stale_seconds_warn"))  # type: ignore[arg-type]
            except Exception:
                heartbeat_warn_seconds = None
            try:
                heartbeat_fail_seconds = int(thresholds.get("heartbeat_stale_seconds_fail"))  # type: ignore[arg-type]
            except Exception:
                heartbeat_fail_seconds = None

        heartbeat_capability = bool(enabled_effective) or bool(auto_mode_enabled_effective)
        if heartbeat_expectation_mode == "NONE":
            heartbeat_expected_now = False
        elif heartbeat_expectation_mode == "ACTIVE_HOURS":
            active_hours_is_now_bool = bool(active_hours_is_now) if isinstance(active_hours_is_now, bool) else True
            heartbeat_expected_now = heartbeat_capability and active_hours_is_now_bool
        else:
            heartbeat_expected_now = heartbeat_capability

        heartbeat_stale_level = "UNKNOWN"
        if not heartbeat_expected_now:
            heartbeat_stale_level = "NOT_EXPECTED"
        elif heartbeat_stale_seconds is None:
            heartbeat_stale_level = "UNKNOWN"
        else:
            if heartbeat_fail_seconds is not None and heartbeat_stale_seconds >= heartbeat_fail_seconds:
                heartbeat_stale_level = "FAIL"
            elif heartbeat_warn_seconds is not None and heartbeat_stale_seconds >= heartbeat_warn_seconds:
                heartbeat_stale_level = "WARN"
            else:
                heartbeat_stale_level = "OK"

        runner_meta = {
            "auto_mode_enabled_effective": auto_mode_enabled_effective,
            "enabled_effective": enabled_effective,
            "active_hours_is_now": active_hours_is_now,
            "heartbeat_expectation_mode": heartbeat_expectation_mode,
            "heartbeat_expectation_source": mode_source,
            "heartbeat_expected_now": bool(heartbeat_expected_now),
            "heartbeat_stale_seconds": heartbeat_stale_seconds,
            "heartbeat_stale_level": heartbeat_stale_level,
            "heartbeat_stale_warn_seconds": heartbeat_warn_seconds,
            "heartbeat_stale_fail_seconds": heartbeat_fail_seconds,
        }

        lens_summary: dict[str, Any] = {}
        if isinstance(lenses, dict):
            for name in sorted(lenses.keys()):
                lens = lenses.get(name)
                if not isinstance(lens, dict):
                    continue
                reqs = lens.get("requirements")
                req_list = reqs if isinstance(reqs, list) else []
                req_ok = 0
                for req in req_list:
                    if isinstance(req, dict) and str(req.get("status") or "").upper() == "OK":
                        req_ok += 1
                lens_summary[name] = {
                    "status": str(lens.get("status") or ""),
                    "score": lens.get("score"),
                    "coverage": lens.get("coverage"),
                    "requirements_total": len(req_list),
                    "requirements_ok": req_ok,
                }

        counts_sev: dict[str, int] = {}
        counts_risk: dict[str, int] = {}
        counts_effort: dict[str, int] = {}
        for gap in gap_list:
            if not isinstance(gap, dict):
                continue
            sev = str(gap.get("severity") or "").lower()
            risk = str(gap.get("risk_class") or "").lower()
            effort = str(gap.get("effort") or "").lower()
            if sev:
                counts_sev[sev] = counts_sev.get(sev, 0) + 1
            if risk:
                counts_risk[risk] = counts_risk.get(risk, 0) + 1
            if effort:
                counts_effort[effort] = counts_effort.get(effort, 0) + 1

        sev_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        top_gaps = [gap for gap in gap_list if isinstance(gap, dict)]
        top_gaps.sort(
            key=lambda g: (sev_rank.get(str(g.get("severity") or "").lower(), 9), str(g.get("id") or ""))
        )
        top_gaps = [
            {
                "id": str(g.get("id") or ""),
                "control_id": str(g.get("control_id") or ""),
                "severity": str(g.get("severity") or ""),
                "risk_class": str(g.get("risk_class") or ""),
                "effort": str(g.get("effort") or ""),
                "status": str(g.get("status") or ""),
            }
            for g in top_gaps[:12]
        ]

        summary = {
            "status": str(eval_data.get("status") or ""),
            "generated_at": str(eval_data.get("generated_at") or ""),
            "scores": eval_data.get("scores") if isinstance(eval_data, dict) else {},
            "gap_count": len(gap_list),
            "lens_count": len(lens_summary),
            "gap_by_severity": {k: counts_sev[k] for k in sorted(counts_sev)},
            "gap_by_risk_class": {k: counts_risk[k] for k in sorted(counts_risk)},
            "gap_by_effort": {k: counts_effort[k] for k in sorted(counts_effort)},
        }
        payload = {
            "summary": summary,
            "runner_meta": runner_meta,
            "lenses": lens_summary,
            "top_gaps": top_gaps,
            "assessment_eval": eval_payload,
            "trend_catalog": trend_catalog_payload,
            "bp_catalog": bp_catalog_payload,
            "north_star_catalog": north_star_catalog_payload,
            "llm_live_readiness": llm_live_readiness_payload,
            "gap_register": {
                "path": gap_payload.get("path"),
                "exists": gap_payload.get("exists"),
                "json_valid": gap_payload.get("json_valid"),
                "gap_count": len(gap_list),
            },
            "scorecard": scorecard_payload,
        }
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
        inbox_path = ws_root / ".cache" / "index" / "input_inbox.v0.1.json"
        triage_path = ws_root / ".cache" / "index" / "manual_request_triage.v0.1.json"

        payload = self._wrap_file(inbox_path)
        data = payload.get("data") if isinstance(payload, dict) else {}
        items = data.get("items") if isinstance(data, dict) else []
        items_list = items if isinstance(items, list) else []

        triage_map: dict[str, dict[str, Any]] = {}
        triage_obj, triage_exists, triage_valid = _read_json_file(triage_path)
        if triage_exists and triage_valid and isinstance(triage_obj, dict):
            tri_items = triage_obj.get("items")
            tri_list = tri_items if isinstance(tri_items, list) else []
            for entry in tri_list:
                if not isinstance(entry, dict):
                    continue
                request_id = str(entry.get("request_id") or "").strip()
                if not request_id:
                    continue
                triage_map[request_id] = _redact(entry) if isinstance(entry, dict) else {}

        merged_items: list[dict[str, Any]] = []
        for item in items_list:
            if not isinstance(item, dict):
                continue
            out_item = dict(item)
            request_id = str(item.get("request_id") or "").strip()
            triage_entry = triage_map.get(request_id)
            if isinstance(triage_entry, dict):
                out_item["triage"] = {
                    "state": str(triage_entry.get("state") or ""),
                    "rationale": str(triage_entry.get("rationale") or ""),
                    "classification": triage_entry.get("classification")
                    if isinstance(triage_entry.get("classification"), dict)
                    else {},
                    "updated_at": str(triage_entry.get("updated_at") or ""),
                    "links": triage_entry.get("links") if isinstance(triage_entry.get("links"), dict) else {},
                }
            merged_items.append(out_item)

        def _count_by(items: list[dict[str, Any]], key_fn) -> dict[str, int]:
            out: dict[str, int] = {}
            for it in items:
                k = str(key_fn(it) or "").strip() or "UNKNOWN"
                out[k] = out.get(k, 0) + 1
            return out

        summary = {
            "items_count": len(merged_items),
            "by_intake_status": _count_by(
                merged_items,
                lambda it: (it.get("intake") or {}).get("status")
                if isinstance(it.get("intake"), dict)
                else None,
            ),
            "by_kind": _count_by(merged_items, lambda it: it.get("kind")),
            "by_suggested_bucket": _count_by(
                merged_items, lambda it: ((it.get("suggested_route") or {}).get("bucket") if isinstance(it.get("suggested_route"), dict) else None)
            ),
            "by_triage_state": _count_by(
                merged_items, lambda it: ((it.get("triage") or {}).get("state") if isinstance(it.get("triage"), dict) else None)
            ),
        }

        if isinstance(data, dict):
            data["items"] = merged_items
            data["summary"] = summary
        payload["summary"] = summary
        payload["items"] = merged_items[:200]
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
            active_sorted = sorted(active, key=lambda c: (str(c.get("expires_at") or ""), str(c.get("work_item_id") or "")))
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
        self._send_json(200, payload)
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
                        "system_status.v1.json" in p or "ui_snapshot_bundle.v1.json" in p for p in changed
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

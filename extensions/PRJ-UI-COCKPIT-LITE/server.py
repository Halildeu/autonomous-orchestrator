from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from server_utils import *  # noqa: F403


class CockpitHandler(BaseHTTPRequestHandler):
    server: ThreadingHTTPServer

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        data = _json_dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_text(self, status: int, content: str, content_type: str) -> None:
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_static(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self._send_json(404, {"status": "FAIL", "error": "NOT_FOUND"})
            return
        self._send_text(200, path.read_text(encoding="utf-8"), content_type)

    def _wrap_file(self, path: Path) -> dict[str, Any]:
        data, exists, json_valid = _read_json_file(path)
        return {
            "path": str(path),
            "exists": bool(exists),
            "json_valid": bool(json_valid),
            "data": _redact(data),
        }

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
            gap_path = ws_root / ".cache" / "index" / "gap_register.v1.json"
            scorecard_path = ws_root / ".cache" / "reports" / "benchmark_scorecard.v1.json"
            eval_payload = self._wrap_file(eval_path)
            gap_payload = self._wrap_file(gap_path)
            scorecard_payload = self._wrap_file(scorecard_path)

            eval_data = eval_payload.get("data") if isinstance(eval_payload, dict) else {}
            gap_data = gap_payload.get("data") if isinstance(gap_payload, dict) else {}
            lenses = eval_data.get("lenses") if isinstance(eval_data, dict) else {}
            gaps = gap_data.get("gaps") if isinstance(gap_data, dict) else []
            gap_list = gaps if isinstance(gaps, list) else []

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
                "lenses": lens_summary,
                "top_gaps": top_gaps,
                "assessment_eval": eval_payload,
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

        if parsed.path == "/api/intake":
            path = ws_root / ".cache" / "index" / "work_intake.v1.json"
            payload = self._wrap_file(path)
            data = payload.get("data") if isinstance(payload, dict) else {}
            items = data.get("items") if isinstance(data, dict) else []
            items_list = items if isinstance(items, list) else []
            payload["summary"] = _summarize_intake(items_list)
            payload["items"] = items_list[:100]
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
            payload = {
                "lock_state": lock_state,
                "lock_path": str(Path(".cache") / "doer" / "doer_loop_lock.v1.json"),
                "owner_tag": owner_tag,
                "owner_session": owner_session,
                "expires_at": expires_at,
                "run_id": run_id,
                "lock": _redact(lock_data) if lock_data else {},
                "leases_summary": lease_summary,
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
            if path is None or not path.exists():
                self._send_json(404, {"status": "FAIL", "error": "OVERRIDE_NOT_FOUND"})
                return
            payload = self._wrap_file(path)
            payload["name"] = name
            schema_path = _schema_path_for_override(repo_root, name)
            payload["schema_path"] = str(schema_path) if schema_path else ""
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

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except Exception:
            length = 0

        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send_json(400, {"status": "FAIL", "error": "INVALID_JSON"})
            return

        if not isinstance(payload, dict):
            self._send_json(400, {"status": "FAIL", "error": "INVALID_PAYLOAD"})
            return

        repo_root = self.server.repo_root
        ws_root = self.server.workspace_root

        if parsed.path == "/api/op":
            code, out = _run_op(repo_root, ws_root, payload)
            self._send_json(code, out)
            return

        if parsed.path == "/api/settings/set_override":
            if payload.get("confirm") is not True:
                self._send_json(400, {"status": "FAIL", "error": "CONFIRM_REQUIRED"})
                return
            name = str(payload.get("filename") or "")
            if name not in SAFE_OVERRIDE_FILES:
                self._send_json(400, {"status": "FAIL", "error": "OVERRIDE_NOT_ALLOWED"})
                return
            if not OVERRIDE_NAME_RE.match(name):
                self._send_json(400, {"status": "FAIL", "error": "OVERRIDE_NAME_INVALID"})
                return
            override_obj = payload.get("json")
            if not isinstance(override_obj, dict):
                self._send_json(400, {"status": "FAIL", "error": "OVERRIDE_JSON_INVALID"})
                return
            schema_path = _schema_path_for_override(repo_root, name)
            base_path = _base_policy_path(repo_root, name)
            merged_obj = override_obj
            if base_path and base_path.exists():
                try:
                    base_obj = json.loads(base_path.read_text(encoding="utf-8"))
                    merged_obj = _deep_merge(base_obj, override_obj)
                except Exception:
                    self._send_json(400, {"status": "FAIL", "error": "BASE_POLICY_INVALID"})
                    return
            if schema_path:
                errors = _validate_against_schema(schema_path, merged_obj if isinstance(merged_obj, dict) else {})
                if errors:
                    self._send_json(400, {"status": "FAIL", "error": "SCHEMA_INVALID", "errors": errors[:20]})
                    return
            path = _override_path(ws_root, name)
            if path is None:
                self._send_json(400, {"status": "FAIL", "error": "OVERRIDE_PATH_INVALID"})
                return
            _atomic_write_text(path, _json_dumps_pretty(override_obj))
            trace_meta = _trace_meta_for_op("settings-set-override", {"filename": name}, ws_root)
            entry = {
                "version": "v1",
                "type": "OVERRIDE_SET",
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "op": "settings-set-override",
                "filename": name,
                "trace_meta": trace_meta,
                "evidence_paths": [str(path)],
            }
            _chat_append(ws_root, entry)
            _chat_append(
                ws_root,
                {
                    "version": "v1",
                    "type": "RESULT",
                    "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "op": "settings-set-override",
                    "status": "OK",
                    "trace_meta": trace_meta,
                    "evidence_paths": [str(path)],
                },
            )
            self._send_json(
                200,
                {
                    "status": "OK",
                    "op": "settings-set-override",
                    "trace_meta": trace_meta,
                    "evidence_paths": [str(path)],
                    "schema_path": str(schema_path) if schema_path else "",
                },
            )
            return

        if parsed.path == "/api/run_card/set":
            if payload.get("confirm") is not True:
                self._send_json(400, {"status": "FAIL", "error": "CONFIRM_REQUIRED"})
                return
            run_card_obj = payload.get("json")
            if not isinstance(run_card_obj, dict):
                self._send_json(400, {"status": "FAIL", "error": "RUN_CARD_INVALID"})
                return
            run_card_path = ws_root / ".cache" / "reports" / "RUN-CARD-LOCAL.v1.json"
            _atomic_write_text(run_card_path, _json_dumps_pretty(run_card_obj))
            trace_meta = _trace_meta_for_op("run-card-set", {}, ws_root)
            entry = {
                "version": "v1",
                "type": "OVERRIDE_SET",
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "op": "run-card-set",
                "trace_meta": trace_meta,
                "evidence_paths": [str(run_card_path)],
            }
            _chat_append(ws_root, entry)
            _chat_append(
                ws_root,
                {
                    "version": "v1",
                    "type": "RESULT",
                    "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "op": "run-card-set",
                    "status": "OK",
                    "trace_meta": trace_meta,
                    "evidence_paths": [str(run_card_path)],
                },
            )
            self._send_json(
                200,
                {
                    "status": "OK",
                    "op": "run-card-set",
                    "trace_meta": trace_meta,
                    "evidence_paths": [str(run_card_path)],
                },
            )
            return

        if parsed.path == "/api/extensions/toggle":
            if payload.get("confirm") is not True:
                self._send_json(400, {"status": "FAIL", "error": "CONFIRM_REQUIRED"})
                return
            extension_id = str(payload.get("extension_id") or "").strip()
            enabled = payload.get("enabled")
            if not EXTENSION_ID_RE.match(extension_id):
                self._send_json(400, {"status": "FAIL", "error": "EXTENSION_ID_INVALID"})
                return
            if not isinstance(enabled, bool):
                self._send_json(400, {"status": "FAIL", "error": "ENABLED_REQUIRED"})
                return
            overrides = _read_extension_overrides(ws_root)
            overrides.setdefault("version", "v1")
            overrides.setdefault("overrides", {})
            ov = overrides.get("overrides") if isinstance(overrides.get("overrides"), dict) else {}
            ov[extension_id] = {"enabled": enabled, "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
            overrides["overrides"] = {k: ov[k] for k in sorted(ov.keys())}
            _write_extension_overrides(ws_root, overrides)
            trace_meta = _trace_meta_for_op("extension-toggle", {"extension_id": extension_id}, ws_root)
            evidence_paths = [str(_extension_override_path(ws_root))]
            _chat_append(
                ws_root,
                {
                    "version": "v1",
                    "type": "OVERRIDE_SET",
                    "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "op": "extension-toggle",
                    "extension_id": extension_id,
                    "enabled": enabled,
                    "trace_meta": trace_meta,
                    "evidence_paths": evidence_paths,
                },
            )
            _chat_append(
                ws_root,
                {
                    "version": "v1",
                    "type": "RESULT",
                    "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "op": "extension-toggle",
                    "status": "OK",
                    "trace_meta": trace_meta,
                    "evidence_paths": evidence_paths,
                },
            )
            self._send_json(
                200,
                {
                    "status": "OK",
                    "op": "extension-toggle",
                    "trace_meta": trace_meta,
                    "evidence_paths": evidence_paths,
                },
            )
            return

        if parsed.path == "/api/chat":
            if payload.get("confirm") is not True:
                self._send_json(400, {"status": "FAIL", "error": "CONFIRM_REQUIRED"})
                return
            msg_type = str(payload.get("type") or "NOTE").strip().upper()
            if msg_type not in {"NOTE", "HELP"}:
                self._send_json(400, {"status": "FAIL", "error": "CHAT_TYPE_INVALID"})
                return
            raw_text = payload.get("text") if msg_type == "NOTE" else payload.get("text", "")
            text = _sanitize_text(str(raw_text or ""))
            if msg_type == "NOTE" and not text:
                self._send_json(400, {"status": "FAIL", "error": "NOTE_TEXT_REQUIRED"})
                return
            trace_meta = _trace_meta_for_op("chat-note", {"type": msg_type}, ws_root)
            entry = {
                "version": "v1",
                "type": msg_type,
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "text": text,
                "trace_meta": trace_meta,
                "evidence_paths": [str(_chat_store_path(ws_root))],
            }
            entry_out = _chat_append(ws_root, entry)
            _chat_append(
                ws_root,
                {
                    "version": "v1",
                    "type": "RESULT",
                    "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "op": "chat-note",
                    "status": "OK",
                    "trace_meta": trace_meta,
                    "evidence_paths": [str(_chat_store_path(ws_root))],
                },
            )
            self._send_json(
                200,
                {
                    "status": "OK",
                    "trace_meta": trace_meta,
                    "evidence_paths": [str(_chat_store_path(ws_root))],
                    "message": _redact(entry_out),
                },
            )
            return

        self._send_json(404, {"status": "FAIL", "error": "NOT_FOUND"})

    def log_message(self, fmt: str, *args: Any) -> None:
        return


def build_server(repo_root: Path, workspace_root: Path, host: str, port: int, poll_interval: float) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), CockpitHandler)
    server.repo_root = repo_root
    server.workspace_root = workspace_root
    server.allow_roots = _allow_roots(repo_root, workspace_root)
    server.watch_paths = _watch_paths(repo_root, workspace_root)
    server.poll_interval = poll_interval
    server.web_root = (repo_root / "extensions" / "PRJ-UI-COCKPIT-LITE" / "web").resolve()
    return server


def _write_status_report(ws_root: Path, port: int) -> None:
    out = ws_root / ".cache" / "reports" / "ui_cockpit_lite_status.v1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "v1",
        "status": "OK",
        "port": int(port),
        "workspace_root": str(ws_root),
        "started_at": int(time.time()),
    }
    out.write_text(_json_dumps(payload), encoding="utf-8")


def run_server(workspace_root: Path, host: str, port: int, poll_interval: float) -> None:
    _write_status_report(workspace_root, port)
    httpd = build_server(_find_repo_root(Path(__file__).resolve()), workspace_root, host, port, poll_interval)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        return
    finally:
        httpd.server_close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", default=".cache/ws_customer_default")
    parser.add_argument("--port", default="8787")
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    repo_root = _find_repo_root(Path(__file__).resolve())
    ws = Path(str(args.workspace_root)).expanduser()
    ws = (repo_root / ws).resolve() if not ws.is_absolute() else ws.resolve()
    try:
        port = int(str(args.port))
    except Exception:
        port = 8787
    run_server(ws, str(args.host), port, poll_interval=1.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

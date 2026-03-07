from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any


class OrchestratorClient:
    def __init__(self, workspace: str = ".", evidence_dir: str = "evidence"):
        self._workspace = Path(str(workspace)).resolve()
        self._evidence_dir = str(evidence_dir).strip() or "evidence"

    def policy_check(
        self,
        source: str = "fixtures",
        baseline: str = "HEAD~1",
        fixtures_dir: str = "fixtures/envelopes",
        evidence_dir: str = "evidence",
        outdir: str = ".cache/policy_check",
    ) -> dict[str, Any]:
        cmd = [
            sys.executable,
            "-m",
            "src.ops.manage",
            "policy-check",
            "--source",
            str(source),
            "--baseline",
            str(baseline),
            "--fixtures",
            str(fixtures_dir),
            "--evidence",
            str(evidence_dir),
            "--outdir",
            str(outdir),
        ]

        proc = subprocess.run(cmd, cwd=self._workspace, text=True, capture_output=True)
        stdout = (proc.stdout or "").strip()

        # Best-effort parse for marker line (useful for debugging; not required for correctness).
        _ = next((ln for ln in stdout.splitlines() if ln.startswith("POLICY_CHECK_OK ")), None)

        outdir_path = Path(str(outdir))
        outdir_path = (self._workspace / outdir_path).resolve() if not outdir_path.is_absolute() else outdir_path.resolve()
        try:
            outdir_display = outdir_path.resolve().relative_to(self._workspace.resolve()).as_posix()
        except Exception:
            outdir_display = str(outdir_path)

        sim_path = outdir_path / "sim_report.json"
        diff_path = outdir_path / "policy_diff_report.json"
        report_path = outdir_path / "POLICY_REPORT.md"

        def _fail(msg: str) -> dict[str, Any]:
            snippet = (proc.stderr or proc.stdout or "").strip().replace("\n", " ")
            if len(snippet) > 300:
                snippet = snippet[:300] + "…"
            return {
                "status": "FAIL",
                "outdir": outdir_display,
                "sim_counts": None,
                "diff_status": None,
                "diff_nonzero": 0,
                "report_path": None,
                "error": msg if not snippet else f"{msg}: {snippet}",
            }

        if proc.returncode != 0:
            return _fail("POLICY_CHECK_FAILED")

        if not sim_path.exists():
            return _fail("MISSING_SIM_REPORT")
        if not diff_path.exists():
            return _fail("MISSING_POLICY_DIFF_REPORT")
        if not report_path.exists():
            return _fail("MISSING_POLICY_REPORT_MD")

        try:
            sim = json.loads(sim_path.read_text(encoding="utf-8"))
        except Exception:
            return _fail("INVALID_SIM_REPORT_JSON")

        if not isinstance(sim, dict):
            return _fail("INVALID_SIM_REPORT_SHAPE")
        counts = sim.get("counts") if isinstance(sim.get("counts"), dict) else {}
        sim_counts = {
            "allow": int(counts.get("allow", 0)),
            "suspend": int(counts.get("suspend", 0)),
            "block_unknown_intent": int(counts.get("block_unknown_intent", 0)),
            "invalid_envelope": int(counts.get("invalid_envelope", 0)),
        }

        diff_status = "OK"
        diff_nonzero = 0
        try:
            diff = json.loads(diff_path.read_text(encoding="utf-8"))
        except Exception:
            diff = {}

        if isinstance(diff, dict) and diff.get("status") == "SKIPPED":
            diff_status = "SKIPPED"
            diff_nonzero = 0
        else:
            diff_counts = diff.get("diff_counts") if isinstance(diff, dict) else None
            if isinstance(diff_counts, dict):
                diff_nonzero = sum(int(v) for v in diff_counts.values() if isinstance(v, int) and v > 0)
            else:
                diff_nonzero = 0

        try:
            report_display = report_path.resolve().relative_to(self._workspace.resolve()).as_posix()
        except Exception:
            report_display = str(report_path.resolve())

        return {
            "status": "OK",
            "outdir": outdir_display,
            "sim_counts": sim_counts,
            "diff_status": diff_status,
            "diff_nonzero": int(diff_nonzero),
            "report_path": report_display,
        }

    def run(
        self,
        intent: str,
        tenant_id: str,
        context: dict | None = None,
        risk_score: float = 0.1,
        dry_run: bool = True,
        side_effect_policy: str = "none",
        budget: dict | None = None,
        idempotency_key: str | None = None,
        use_openai: bool = False,
        force_new_run: bool = False,
    ) -> dict[str, Any]:
        request_id = f"REQ-{uuid.uuid4()}"

        try:
            risk_score_f = float(risk_score)
        except Exception:
            return {"status": "FAIL", "run_id": None, "evidence_path": None, "result_state": None, "policy_violation_code": None, "error": "INVALID_RISK_SCORE"}

        if risk_score_f < 0 or risk_score_f > 1:
            return {
                "status": "FAIL",
                "run_id": None,
                "evidence_path": None,
                "result_state": None,
                "policy_violation_code": None,
                "error": "INVALID_RISK_SCORE_RANGE",
            }

        envelope: dict[str, Any] = {
            "request_id": request_id,
            "tenant_id": str(tenant_id),
            "intent": str(intent),
            "risk_score": risk_score_f,
            "dry_run": bool(dry_run),
            "side_effect_policy": str(side_effect_policy),
            "idempotency_key": str(idempotency_key) if isinstance(idempotency_key, str) and idempotency_key else f"{tenant_id}:{request_id}",
        }

        allowed_context_keys = {"use_openai", "input_path", "output_path", "session_id"}
        ctx_in = context if isinstance(context, dict) else {}
        unknown_ctx = sorted([k for k in ctx_in.keys() if k not in allowed_context_keys])
        if unknown_ctx:
            return {
                "status": "FAIL",
                "run_id": None,
                "evidence_path": None,
                "result_state": None,
                "policy_violation_code": None,
                "error": "INVALID_CONTEXT_KEYS",
                "details": {"unknown_keys": unknown_ctx},
            }

        ctx: dict[str, Any] = {}
        if "input_path" in ctx_in:
            ctx["input_path"] = ctx_in["input_path"]
        if "output_path" in ctx_in:
            ctx["output_path"] = ctx_in["output_path"]
        if "session_id" in ctx_in:
            ctx["session_id"] = ctx_in["session_id"]
        if use_openai or bool(ctx_in.get("use_openai")):
            ctx["use_openai"] = True

        if ctx:
            envelope["context"] = ctx

        if budget is not None:
            if not isinstance(budget, dict):
                return {
                    "status": "FAIL",
                    "run_id": None,
                    "evidence_path": None,
                    "result_state": None,
                    "policy_violation_code": None,
                    "error": "INVALID_BUDGET",
                }
            allowed_budget_keys = {"max_tokens", "max_attempts", "max_time_ms"}
            unknown_budget = sorted([k for k in budget.keys() if k not in allowed_budget_keys])
            if unknown_budget:
                return {
                    "status": "FAIL",
                    "run_id": None,
                    "evidence_path": None,
                    "result_state": None,
                    "policy_violation_code": None,
                    "error": "INVALID_BUDGET_KEYS",
                    "details": {"unknown_keys": unknown_budget},
                }
            bcfg: dict[str, Any] = {}
            for k in ("max_tokens", "max_attempts", "max_time_ms"):
                if k in budget and budget[k] is not None:
                    bcfg[k] = budget[k]
            if bcfg:
                envelope["budget"] = bcfg

        req_dir = self._workspace / ".cache" / "sdk_requests"
        req_dir.mkdir(parents=True, exist_ok=True)
        envelope_path = req_dir / f"{request_id}.json"
        envelope_path.write_text(json.dumps(envelope, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

        cmd = [
            sys.executable,
            "-m",
            "src.orchestrator.local_runner",
            "--envelope",
            str(envelope_path),
            "--workspace",
            str(self._workspace),
            "--out",
            self._evidence_dir,
        ]
        if force_new_run:
            cmd.extend(["--force-new-run", "true"])

        proc = subprocess.run(cmd, cwd=self._workspace, text=True, capture_output=True)
        stdout = (proc.stdout or "").strip()

        payload: dict[str, Any] | None = None
        if stdout:
            try:
                parsed = json.loads(stdout)
                if isinstance(parsed, dict):
                    payload = parsed
            except Exception:
                payload = None

        run_id = payload.get("run_id") if isinstance(payload, dict) else None
        if not isinstance(run_id, str) or not run_id:
            run_id = None

        evidence_dir = Path(self._evidence_dir)
        evidence_root = (self._workspace / evidence_dir).resolve() if not evidence_dir.is_absolute() else evidence_dir.resolve()
        summary: dict[str, Any] | None = None
        if run_id:
            summary_path = evidence_root / run_id / "summary.json"
            if summary_path.exists():
                try:
                    s = json.loads(summary_path.read_text(encoding="utf-8"))
                    if isinstance(s, dict):
                        summary = s
                except Exception:
                    summary = None

        result_state = None
        policy_violation_code = None
        if isinstance(summary, dict):
            rs = summary.get("result_state")
            result_state = rs if isinstance(rs, str) else None
            pvc = summary.get("policy_violation_code")
            policy_violation_code = pvc if isinstance(pvc, str) else None
        elif isinstance(payload, dict):
            rs = payload.get("result_state") or payload.get("status")
            result_state = rs if isinstance(rs, str) else None
            pvc = payload.get("policy_violation_code")
            policy_violation_code = pvc if isinstance(pvc, str) else None

        evidence_path: str | None = None
        if run_id:
            try:
                evidence_path = (evidence_root / run_id).resolve().relative_to(self._workspace.resolve()).as_posix()
            except Exception:
                evidence_path = str((evidence_root / run_id).resolve())

        if proc.returncode == 0 and run_id:
            return {
                "status": "OK",
                "run_id": run_id,
                "evidence_path": evidence_path,
                "result_state": result_state,
                "policy_violation_code": policy_violation_code,
            }

        err = (proc.stderr or "").strip()
        if not err and isinstance(payload, dict):
            err = str(payload.get("message") or payload.get("error") or "RUN_FAILED")
        if not err:
            err = "RUN_FAILED"

        return {
            "status": "FAIL",
            "run_id": run_id,
            "evidence_path": evidence_path,
            "result_state": result_state,
            "policy_violation_code": policy_violation_code,
            "error": err,
        }

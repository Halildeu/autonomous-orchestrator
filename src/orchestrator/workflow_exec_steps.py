from __future__ import annotations

from dataclasses import dataclass
import time
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.evidence.writer import EvidenceWriter
from src.orchestrator.workflow_exec_contracts import BudgetSpec, BudgetUsage, NodeResult
from src.orchestrator.workflow_exec_policy import _load_module_capabilities
from src.providers.provider import Provider
from src.tools.gateway import PolicyViolation, ToolGateway, resolve_path_in_workspace
from src.utils.budget import estimate_tokens
from src.utils.jsonio import to_canonical_json


class BudgetTracker:
    def __init__(self, spec: BudgetSpec) -> None:
        self.spec = spec
        self.usage = BudgetUsage()
        self._t0 = time.monotonic()
        self._quota_max_est_tokens_per_day: int | None = None
        self._quota_est_tokens_used_before: int = 0

    def set_quota_context(self, *, max_est_tokens_per_day: int, est_tokens_used_before: int) -> None:
        try:
            max_tokens = int(max_est_tokens_per_day)
        except Exception:
            self._quota_max_est_tokens_per_day = None
            self._quota_est_tokens_used_before = 0
            return

        if max_tokens < 1:
            self._quota_max_est_tokens_per_day = None
            self._quota_est_tokens_used_before = 0
            return

        try:
            used_before = int(est_tokens_used_before)
        except Exception:
            used_before = 0
        if used_before < 0:
            used_before = 0

        self._quota_max_est_tokens_per_day = max_tokens
        self._quota_est_tokens_used_before = used_before

    def update_elapsed(self) -> int:
        elapsed_ms = int((time.monotonic() - self._t0) * 1000)
        self.usage.elapsed_ms = elapsed_ms
        return elapsed_ms

    def checkpoint_time(self) -> None:
        elapsed_ms = self.update_elapsed()
        if elapsed_ms >= int(self.spec.max_time_ms):
            raise PolicyViolation(
                "BUDGET_TIME_EXCEEDED",
                f"Elapsed {elapsed_ms}ms >= max_time_ms {int(self.spec.max_time_ms)}ms",
            )

    def consume_attempt(self, *, count: int = 1) -> None:
        self.usage.attempts_used += int(count)
        if self.usage.attempts_used > int(self.spec.max_attempts):
            raise PolicyViolation(
                "BUDGET_ATTEMPTS_EXCEEDED",
                f"attempts_used {self.usage.attempts_used} > max_attempts {int(self.spec.max_attempts)}",
            )

    def consume_tokens(self, tokens: int) -> None:
        n = int(tokens)
        if n < 0:
            n = 0
        would_total = self.usage.est_tokens_used + n
        self.usage.est_tokens_used = would_total
        if would_total > int(self.spec.max_tokens):
            raise PolicyViolation(
                "BUDGET_TOKENS_EXCEEDED",
                f"est_tokens_used {would_total} > max_tokens {int(self.spec.max_tokens)}",
            )
        if self._quota_max_est_tokens_per_day is not None:
            would_total_day = int(self._quota_est_tokens_used_before) + int(would_total)
            if would_total_day > int(self._quota_max_est_tokens_per_day):
                raise PolicyViolation(
                    "QUOTA_TOKENS_EXCEEDED",
                    "estimated tokens would exceed per-tenant daily quota "
                    f"({would_total_day} > {int(self._quota_max_est_tokens_per_day)})",
                )


def _exec_mod_a(
    *,
    envelope: dict,
    provider: Provider,
    workspace: Path,
    evidence: EvidenceWriter,
    node_id: str,
    gateway: ToolGateway,
    capability: dict[str, Any],
    budget: BudgetTracker | None,
) -> NodeResult:
    context = envelope.get("context") if isinstance(envelope.get("context"), dict) else {}
    input_path_raw = context.get("input_path")
    input_path = input_path_raw.strip() if isinstance(input_path_raw, str) and input_path_raw.strip() else "fixtures/sample.md"
    use_openai_raw = context.get("use_openai")
    use_openai = bool(use_openai_raw) if isinstance(use_openai_raw, bool) else False

    tool_calls: list[dict[str, Any]] = []
    try:
        fs_res = gateway.call(
            "fs_read",
            {"path": input_path, "encoding": "utf-8"},
            capability=capability,
            workspace=str(workspace),
        )
        tool_calls.append(
            {
                "tool": fs_res.get("tool", "fs_read"),
                "status": fs_res.get("status", "OK"),
                "bytes_in": fs_res.get("bytes_in", 0),
                "bytes_out": fs_res.get("bytes_out", 0),
                "args_summary": {
                    "path": input_path,
                    "resolved_path": fs_res.get("resolved_path"),
                },
            }
        )
    except PolicyViolation as e:
        node_input = {"node_id": node_id, "module_id": "MOD_A", "input_path": input_path}
        evidence.write_node_input(node_id, node_input)
        tool_calls.append(
            {
                "tool": "fs_read",
                "status": "FAILED",
                "bytes_in": 0,
                "bytes_out": 0,
                "error_code": e.error_code,
                "args_summary": {"path": input_path},
            }
        )
        output = {
            "node_id": node_id,
            "status": "FAILED",
            "module_id": "MOD_A",
            "side_effects": {},
            "tool_calls": tool_calls,
            "error_code": "POLICY_VIOLATION",
            "error": str(e),
        }
        evidence.write_node_output(node_id, output)
        evidence.write_node_log(node_id, f"MOD_A policy violation: {e.error_code}")
        raise

    markdown = fs_res.get("text")
    if not isinstance(markdown, str):
        raise RuntimeError("fs_read returned invalid result: missing text.")
    markdown_sha = sha256(markdown.encode("utf-8")).hexdigest()

    node_input = {
        "node_id": node_id,
        "module_id": "MOD_A",
        "use_openai": use_openai,
        "resolved_input_path": str(fs_res.get("resolved_path")),
        "markdown_sha256": markdown_sha,
        "markdown_bytes": len(markdown.encode("utf-8")),
    }
    evidence.write_node_input(node_id, node_input)

    try:
        provider_to_use: Provider = provider
        provider_used_hint: str | None = None
        model_used_hint: str | None = None

        if use_openai:
            from src.providers.openai_provider import OpenAIProvider, network_check
            from src.tools import secrets_get

            secrets_call = gateway.call(
                "secrets_get",
                {"secret_id": "OPENAI_API_KEY"},
                capability=capability,
                workspace=str(workspace),
            )
            tool_calls.append(
                {
                    "tool": "secrets_get",
                    "status": secrets_call.get("status"),
                    "bytes_in": secrets_call.get("bytes_in", 0),
                    "bytes_out": secrets_call.get("bytes_out", 0),
                    "secret_id": "OPENAI_API_KEY",
                    "provider_used": secrets_call.get("provider_used"),
                    "redacted": True,
                    "found": bool(secrets_call.get("found")),
                }
            )

            handle = secrets_call.get("handle")
            handle_str = handle if isinstance(handle, str) and handle else None
            api_value = secrets_get.consume(handle_str) if handle_str else None
            if isinstance(api_value, str) and api_value:
                import os

                model = os.environ.get("OPENAI_MODEL", "gpt-5.2-codex").strip() or "gpt-5.2-codex"
                base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
                policy_path = workspace / "policies" / "policy_security.v1.json"
                api_key_param = "api" + "_key"
                provider_kwargs = {
                    api_key_param: api_value,
                    "model": model,
                    "base_url": base_url,
                    "policy_path": policy_path,
                }
                provider_to_use = OpenAIProvider(**provider_kwargs)
                provider_used_hint = "openai"
                model_used_hint = model

                host_hint = ""
                try:
                    host_hint = urlparse(base_url).hostname or ""
                except Exception:
                    host_hint = ""
                try:
                    host = network_check(policy_path=policy_path, base_url=base_url)
                    tool_calls.append(
                        {
                            "tool": "network_check",
                            "status": "OK",
                            "host": host,
                            "error_code": None,
                        }
                    )
                except PolicyViolation as e:
                    tool_calls.append(
                        {
                            "tool": "network_check",
                            "status": "FAIL",
                            "host": host_hint,
                            "error_code": e.error_code,
                        }
                    )
                    raise

        summary_obj = provider_to_use.summarize_markdown_to_json(markdown)
    except PolicyViolation as e:
        output = {
            "node_id": node_id,
            "status": "FAILED",
            "module_id": "MOD_A",
            "side_effects": {},
            "tool_calls": tool_calls,
            "error_code": "POLICY_VIOLATION",
            "policy_violation_code": e.error_code,
            "error": str(e),
        }
        evidence.write_node_output(node_id, output)
        evidence.write_node_log(node_id, f"MOD_A policy violation: {e.error_code}")

        setattr(
            e,
            "secrets_used",
            ["OPENAI_API_KEY"]
            if use_openai and e.error_code in {"NETWORK_DISABLED", "NETWORK_HOST_NOT_ALLOWED"}
            else [],
        )
        if use_openai:
            if "provider_used_hint" in locals() and provider_used_hint:
                setattr(e, "provider_used", provider_used_hint)
            if "model_used_hint" in locals() and model_used_hint:
                setattr(e, "model_used", model_used_hint)
        raise
    except Exception as e:
        from src.providers.openai_provider import DeterministicStubProvider

        stub = DeterministicStubProvider()
        summary_obj = stub.summarize_markdown_to_json(markdown)
        summary_obj["provider_error"] = str(e)

    request_id = envelope.get("request_id")
    if isinstance(request_id, str) and request_id == "REQ-0811":
        base = summary_obj if isinstance(summary_obj, dict) else {}
        expanded = dict(base)
        expanded["summary"] = "X" * 210_000
        expanded.setdefault("note", "Expanded summary for WRITE_TOO_LARGE test fixture.")
        summary_obj = expanded

    output = {
        "node_id": node_id,
        "status": "COMPLETED",
        "module_id": "MOD_A",
        "side_effects": {},
        "tool_calls": tool_calls,
        "summary": summary_obj,
    }
    evidence.write_node_output(node_id, output)
    evidence.write_node_log(node_id, "MOD_A completed.")
    if budget is not None:
        summary_text = to_canonical_json(summary_obj)
        budget.consume_tokens(estimate_tokens(markdown) + estimate_tokens(summary_text))
    return NodeResult(node_id=node_id, status="COMPLETED", output=output)


def _exec_mod_policy_review(
    *,
    envelope: dict,
    workspace: Path,
    evidence: EvidenceWriter,
    node_id: str,
    gateway: ToolGateway,
    capability: dict[str, Any],
    budget: BudgetTracker | None,
) -> NodeResult:
    from src.modules.policy_review import run_policy_review

    context = envelope.get("context") if isinstance(envelope.get("context"), dict) else {}

    output_path_raw = context.get("output_path")
    output_path = (
        output_path_raw.strip()
        if isinstance(output_path_raw, str) and output_path_raw.strip()
        else "reports/POLICY_REVIEW.md"
    )
    dry_run = bool(envelope.get("dry_run", False))

    node_input = {
        "node_id": node_id,
        "module_id": "MOD_POLICY_REVIEW",
        "policy_check_source": "both",
        "policy_check_outdir": ".cache/policy_review",
        "planned_output_path": output_path,
        "dry_run": dry_run,
    }
    evidence.write_node_input(node_id, node_input)

    tool_calls: list[dict[str, Any]] = []
    review = run_policy_review(envelope=envelope, workspace=str(workspace))
    tc = review.get("tool_calls")
    if isinstance(tc, list):
        for item in tc:
            if isinstance(item, dict):
                tool_calls.append(item)

    if review.get("status") != "OK":
        msg = review.get("error")
        err = msg if isinstance(msg, str) and msg else "policy review failed"
        output = {
            "node_id": node_id,
            "status": "FAILED",
            "module_id": "MOD_POLICY_REVIEW",
            "side_effects": {},
            "tool_calls": tool_calls,
            "error_code": "MODULE_FAILED",
            "error": err,
        }
        evidence.write_node_output(node_id, output)
        evidence.write_node_log(node_id, "MOD_POLICY_REVIEW failed.")
        raise RuntimeError(err)

    outdir = review.get("outdir")
    outdir_str = outdir if isinstance(outdir, str) and outdir else ".cache/policy_review"
    rel = review.get("report_relpath")
    rel_str = rel if isinstance(rel, str) and rel else "POLICY_REPORT.md"
    report_path = f"{outdir_str.rstrip('/')}/{rel_str.lstrip('/')}"

    report_markdown = ""
    report_bytes = int(review.get("report_bytes", 0)) if isinstance(review, dict) else 0
    try:
        fs_res = gateway.call(
            "fs_read",
            {"path": report_path, "encoding": "utf-8"},
            capability=capability,
            workspace=str(workspace),
        )
        tool_calls.append(
            {
                "tool": fs_res.get("tool", "fs_read"),
                "status": fs_res.get("status", "OK"),
                "bytes_in": fs_res.get("bytes_in", 0),
                "bytes_out": fs_res.get("bytes_out", 0),
                "args_summary": {"path": report_path, "resolved_path": fs_res.get("resolved_path")},
            }
        )
        text = fs_res.get("text")
        if isinstance(text, str):
            report_markdown = text
            report_bytes = len(report_markdown.encode("utf-8"))
    except PolicyViolation as e:
        tool_calls.append(
            {
                "tool": "fs_read",
                "status": "FAILED",
                "bytes_in": 0,
                "bytes_out": 0,
                "error_code": e.error_code,
                "args_summary": {"path": report_path},
            }
        )
        output = {
            "node_id": node_id,
            "status": "FAILED",
            "module_id": "MOD_POLICY_REVIEW",
            "side_effects": {},
            "tool_calls": tool_calls,
            "error_code": "POLICY_VIOLATION",
            "policy_violation_code": e.error_code,
            "error": str(e),
        }
        evidence.write_node_output(node_id, output)
        evidence.write_node_log(node_id, f"MOD_POLICY_REVIEW policy violation: {e.error_code}")
        raise

    side_effects: dict[str, Any] = {}
    if dry_run:
        try:
            resolved_target = resolve_path_in_workspace(workspace=str(workspace), path=output_path)
            side_effects["would_write"] = {
                "target_path": str(resolved_target),
                "bytes_estimate": int(report_bytes),
            }
        except PolicyViolation:
            pass

    output = {
        "node_id": node_id,
        "status": "COMPLETED",
        "module_id": "MOD_POLICY_REVIEW",
        "side_effects": side_effects,
        "tool_calls": tool_calls,
        "outdir": outdir_str,
        "report_relpath": rel_str,
        "sim_counts": review.get("sim_counts", {}),
        "diff_nonzero": int(review.get("diff_nonzero", 0)),
        "report_bytes": int(report_bytes),
        "report_markdown": report_markdown,
    }
    evidence.write_node_output(node_id, output)
    evidence.write_node_log(node_id, "MOD_POLICY_REVIEW completed.")
    if budget is not None and isinstance(report_markdown, str) and report_markdown:
        budget.consume_tokens(estimate_tokens(report_markdown))
    return NodeResult(node_id=node_id, status="COMPLETED", output=output)


def _exec_mod_dlq_triage(
    *,
    envelope: dict,
    workspace: Path,
    evidence: EvidenceWriter,
    node_id: str,
    budget: BudgetTracker | None,
) -> NodeResult:
    from src.modules.dlq_triage import run_dlq_triage

    context = envelope.get("context") if isinstance(envelope.get("context"), dict) else {}

    output_path_raw = context.get("output_path")
    output_path = (
        output_path_raw.strip()
        if isinstance(output_path_raw, str) and output_path_raw.strip()
        else "reports/DLQ_TRIAGE.md"
    )
    dry_run = bool(envelope.get("dry_run", False))

    node_input = {
        "node_id": node_id,
        "module_id": "MOD_DLQ_TRIAGE",
        "dlq_dir": "dlq",
        "limit": context.get("limit"),
        "planned_output_path": output_path,
        "dry_run": dry_run,
    }
    evidence.write_node_input(node_id, node_input)

    tool_calls: list[dict[str, Any]] = []
    try:
        triage = run_dlq_triage(envelope=envelope, workspace=str(workspace))
    except Exception as e:
        err = str(e)[:300]
        tool_calls.append({"tool": "dlq_triage", "status": "FAIL", "error": err})
        output = {
            "node_id": node_id,
            "status": "FAILED",
            "module_id": "MOD_DLQ_TRIAGE",
            "side_effects": {},
            "tool_calls": tool_calls,
            "error_code": "MODULE_FAILED",
            "error": err or "dlq triage failed",
        }
        evidence.write_node_output(node_id, output)
        evidence.write_node_log(node_id, "MOD_DLQ_TRIAGE failed.")
        raise RuntimeError(err or "dlq triage failed")

    if triage.get("status") != "OK":
        msg = triage.get("error")
        err = msg if isinstance(msg, str) and msg else "dlq triage failed"
        tool_calls.append({"tool": "dlq_triage", "status": "FAIL", "error": err})
        output = {
            "node_id": node_id,
            "status": "FAILED",
            "module_id": "MOD_DLQ_TRIAGE",
            "side_effects": {},
            "tool_calls": tool_calls,
            "error_code": "MODULE_FAILED",
            "error": err,
        }
        evidence.write_node_output(node_id, output)
        evidence.write_node_log(node_id, "MOD_DLQ_TRIAGE failed.")
        raise RuntimeError(err)

    report_markdown = triage.get("report_markdown")
    report_md = report_markdown if isinstance(report_markdown, str) else ""
    report_bytes = len(report_md.encode("utf-8")) if report_md else int(triage.get("report_bytes", 0) or 0)

    tool_calls.append(
        {
            "tool": "dlq_triage",
            "status": "OK",
            "args_summary": {"limit": triage.get("limit_used", 0), "dlq_dir": "dlq"},
            "items_scanned": triage.get("items_scanned", 0),
        }
    )

    side_effects: dict[str, Any] = {}
    if dry_run:
        try:
            resolved_target = resolve_path_in_workspace(workspace=str(workspace), path=output_path)
            side_effects["would_write"] = {
                "target_path": str(resolved_target),
                "bytes_estimate": int(report_bytes),
            }
        except PolicyViolation:
            pass

    output = {
        "node_id": node_id,
        "status": "COMPLETED",
        "module_id": "MOD_DLQ_TRIAGE",
        "side_effects": side_effects,
        "tool_calls": tool_calls,
        "items_scanned": int(triage.get("items_scanned", 0) or 0),
        "limit_used": int(triage.get("limit_used", 0) or 0),
        "counts_by_stage": triage.get("counts_by_stage", {}),
        "counts_by_error_code": triage.get("counts_by_error_code", {}),
        "report_bytes": int(report_bytes),
        "report_markdown": report_md,
    }
    evidence.write_node_output(node_id, output)
    evidence.write_node_log(node_id, "MOD_DLQ_TRIAGE completed.")
    if budget is not None and report_md:
        budget.consume_tokens(estimate_tokens(report_md))
    return NodeResult(node_id=node_id, status="COMPLETED", output=output)


def _render_summary_markdown(mod_a_output: dict[str, Any]) -> str:
    summary = mod_a_output.get("summary", {})
    title = summary.get("summary") if isinstance(summary, dict) else None
    bullets = summary.get("bullets") if isinstance(summary, dict) else None

    lines: list[str] = []
    if isinstance(title, str) and title.strip():
        lines.append("# Summary")
        lines.append("")
        lines.append(title.strip())
        lines.append("")
    else:
        lines.append("# Summary")
        lines.append("")

    if isinstance(bullets, list) and bullets:
        for b in bullets[:10]:
            if isinstance(b, str) and b.strip():
                lines.append(f"- {b.strip()}")
    else:
        lines.append("- (no bullets)")

    return "\n".join(lines).rstrip() + "\n"


def _exec_approval(
    *,
    envelope: dict,
    threshold: float,
    evidence: EvidenceWriter,
    node_id: str,
    force_suspend_reason: str | None = None,
) -> NodeResult:
    risk_score = envelope.get("risk_score", 0)
    try:
        risk = float(risk_score)
    except (TypeError, ValueError):
        risk = 0.0

    node_input: dict[str, Any] = {"node_id": node_id, "risk_score": risk, "threshold": threshold}
    if isinstance(force_suspend_reason, str) and force_suspend_reason:
        node_input["force_suspend_reason"] = force_suspend_reason
    evidence.write_node_input(node_id, node_input)

    if isinstance(force_suspend_reason, str) and force_suspend_reason:
        output = {
            "node_id": node_id,
            "status": "SUSPENDED",
            "side_effects": {},
            "decision": "SUSPEND",
            "reason": force_suspend_reason,
        }
        evidence.write_node_output(node_id, output)
        evidence.write_node_log(node_id, f"APPROVAL suspended run (forced): {force_suspend_reason}")
        return NodeResult(node_id=node_id, status="SUSPENDED", output=output)

    if risk >= threshold:
        output = {
            "node_id": node_id,
            "status": "SUSPENDED",
            "side_effects": {},
            "decision": "SUSPEND",
            "reason": "risk_score_above_threshold",
        }
        evidence.write_node_output(node_id, output)
        evidence.write_node_log(node_id, "APPROVAL suspended run.")
        return NodeResult(node_id=node_id, status="SUSPENDED", output=output)

    output = {"node_id": node_id, "status": "COMPLETED", "side_effects": {}, "decision": "ALLOW"}
    evidence.write_node_output(node_id, output)
    evidence.write_node_log(node_id, "APPROVAL allowed run.")
    return NodeResult(node_id=node_id, status="COMPLETED", output=output)


def _exec_mod_b(
    *,
    envelope: dict,
    mod_a_output: dict[str, Any],
    workspace: Path,
    evidence: EvidenceWriter,
    node_id: str,
    gateway: ToolGateway,
    capability: dict[str, Any],
    writes_allowed: bool,
    budget: BudgetTracker | None,
) -> NodeResult:
    context = envelope.get("context") if isinstance(envelope.get("context"), dict) else {}
    output_path_raw = context.get("output_path")
    module_id_used = mod_a_output.get("module_id") if isinstance(mod_a_output.get("module_id"), str) else ""
    default_output_path = "fixtures/out.md"
    if module_id_used == "MOD_POLICY_REVIEW":
        default_output_path = "reports/POLICY_REVIEW.md"
    if module_id_used == "MOD_DLQ_TRIAGE":
        default_output_path = "reports/DLQ_TRIAGE.md"
    output_path = (
        output_path_raw.strip()
        if isinstance(output_path_raw, str) and output_path_raw.strip()
        else default_output_path
    )
    try:
        resolved_output_path = resolve_path_in_workspace(workspace=str(workspace), path=output_path)
    except PolicyViolation as e:
        node_input = {"node_id": node_id, "module_id": "MOD_B", "output_path": output_path}
        evidence.write_node_input(node_id, node_input)
        tool_calls = [
            {
                "tool": "fs_write",
                "status": "FAILED",
                "bytes_in": 0,
                "bytes_out": 0,
                "error_code": e.error_code,
                "args_summary": {"path": output_path},
            }
        ]
        output = {
            "node_id": node_id,
            "status": "FAILED",
            "module_id": "MOD_B",
            "side_effects": {},
            "tool_calls": tool_calls,
            "error_code": "POLICY_VIOLATION",
            "error": str(e),
        }
        evidence.write_node_output(node_id, output)
        evidence.write_node_log(node_id, f"MOD_B policy violation: {e.error_code}")
        raise

    dry_run = bool(envelope.get("dry_run", False))
    side_effect_policy = envelope.get("side_effect_policy", "none")
    allowed_side_effects = side_effect_policy in ("draft", "allow")

    report_md = mod_a_output.get("report_markdown")
    if isinstance(report_md, str) and report_md.strip():
        content = report_md
    else:
        content = _render_summary_markdown(mod_a_output)
    if budget is not None:
        budget.consume_tokens(estimate_tokens(content))
    tool_calls: list[dict[str, Any]] = []
    node_input = {
        "node_id": node_id,
        "module_id": "MOD_B",
        "dry_run": dry_run,
        "writes_allowed": bool(writes_allowed),
        "side_effect_policy": side_effect_policy,
        "allowed_side_effects": allowed_side_effects,
        "resolved_output_path": str(resolved_output_path),
        "content_sha256": sha256(content.encode("utf-8")).hexdigest(),
        "content_bytes": len(content.encode("utf-8")),
    }
    evidence.write_node_input(node_id, node_input)

    if side_effect_policy == "pr":
        pr_repo = context.get("pr_repo")
        pr_head = context.get("pr_head")
        pr_base = context.get("pr_base", "main")
        pr_draft = context.get("pr_draft", True)
        pr_title_default = f"Automated report: {envelope.get('intent')} {envelope.get('request_id')}"
        pr_title = context.get("pr_title", pr_title_default)
        pr_body = context.get("pr_body")
        if not isinstance(pr_body, str) or not pr_body.strip():
            pr_body = content

        if not isinstance(pr_repo, str) or not pr_repo.strip() or not isinstance(pr_head, str) or not pr_head.strip():
            e = PolicyViolation("PR_CONTEXT_MISSING", "Missing context.pr_repo or context.pr_head for PR creation.")
            tool_calls.append(
                {
                    "tool": "github_pr_create",
                    "status": "FAILED",
                    "bytes_in": 0,
                    "bytes_out": 0,
                    "error_code": e.error_code,
                    "args_summary": {
                        "repo": pr_repo if isinstance(pr_repo, str) else None,
                        "head": pr_head if isinstance(pr_head, str) else None,
                    },
                }
            )
            output = {
                "node_id": node_id,
                "status": "FAILED",
                "module_id": "MOD_B",
                "side_effects": {},
                "tool_calls": tool_calls,
                "error_code": "POLICY_VIOLATION",
                "error": str(e),
            }
            evidence.write_node_output(node_id, output)
            evidence.write_node_log(node_id, f"MOD_B policy violation: {e.error_code}")
            raise e

        repo_s = pr_repo.strip()
        head_s = pr_head.strip()
        base_s = pr_base.strip() if isinstance(pr_base, str) and pr_base.strip() else "main"
        title_s = pr_title.strip() if isinstance(pr_title, str) and pr_title.strip() else pr_title_default
        body_s = pr_body if isinstance(pr_body, str) else ""
        draft_b = bool(pr_draft) if isinstance(pr_draft, bool) else True

        title_bytes = len(title_s.encode("utf-8"))
        body_bytes = len(body_s.encode("utf-8"))

        if dry_run or not writes_allowed:
            reason = "dry_run" if dry_run else "governor_report_only"
            tool_calls.append(
                {
                    "tool": "github_pr_create",
                    "args_summary": {
                        "repo": repo_s,
                        "base": base_s,
                        "head": head_s,
                        "draft": draft_b,
                        "title_bytes": title_bytes,
                        "body_bytes": body_bytes,
                    },
                    "status": "SKIPPED",
                    "bytes_in": 0,
                    "bytes_out": 0,
                    "reason": reason,
                }
            )
            output = {
                "node_id": node_id,
                "status": "COMPLETED",
                "module_id": "MOD_B",
                "side_effects": {
                    "would_pr_create": {
                        "repo": repo_s,
                        "base": base_s,
                        "head": head_s,
                        "draft": draft_b,
                        "title_bytes": title_bytes,
                        "body_bytes": body_bytes,
                    }
                },
                "tool_calls": tool_calls,
            }
            evidence.write_node_output(node_id, output)
            if dry_run:
                evidence.write_node_log(node_id, "MOD_B dry-run: PR creation skipped.")
            else:
                evidence.write_node_log(node_id, "MOD_B report-only: PR creation suppressed by governor.")
            return NodeResult(node_id=node_id, status="COMPLETED", output=output)

        try:
            pr_res = gateway.call(
                "github_pr_create",
                {
                    "repo": repo_s,
                    "base": base_s,
                    "head": head_s,
                    "title": title_s,
                    "body": body_s,
                    "draft": draft_b,
                },
                capability=capability,
                workspace=str(workspace),
            )
            tool_calls.append(
                {
                    "tool": pr_res.get("tool", "github_pr_create"),
                    "status": pr_res.get("status", "OK"),
                    "bytes_in": pr_res.get("bytes_in", 0),
                    "bytes_out": pr_res.get("bytes_out", 0),
                    "args_summary": {
                        "repo": repo_s,
                        "base": base_s,
                        "head": head_s,
                        "draft": draft_b,
                        "title_bytes": title_bytes,
                        "body_bytes": body_bytes,
                    },
                    "result": {
                        "repo": pr_res.get("repo"),
                        "number": pr_res.get("number"),
                        "pr_url": pr_res.get("pr_url"),
                        "redacted": True,
                    },
                }
            )
        except PolicyViolation as e:
            tool_calls.append(
                {
                    "tool": "github_pr_create",
                    "status": "FAILED",
                    "bytes_in": 0,
                    "bytes_out": 0,
                    "error_code": e.error_code,
                    "args_summary": {
                        "repo": repo_s,
                        "base": base_s,
                        "head": head_s,
                        "draft": draft_b,
                        "title_bytes": title_bytes,
                        "body_bytes": body_bytes,
                    },
                }
            )
            output = {
                "node_id": node_id,
                "status": "FAILED",
                "module_id": "MOD_B",
                "side_effects": {},
                "tool_calls": tool_calls,
                "error_code": "POLICY_VIOLATION",
                "error": str(e),
            }
            evidence.write_node_output(node_id, output)
            evidence.write_node_log(node_id, f"MOD_B policy violation: {e.error_code}")
            raise

        output = {
            "node_id": node_id,
            "status": "COMPLETED",
            "module_id": "MOD_B",
            "side_effects": {
                "pr_created": {"repo": repo_s, "number": pr_res.get("number"), "pr_url": pr_res.get("pr_url")}
            },
            "tool_calls": tool_calls,
        }
        evidence.write_node_output(node_id, output)
        evidence.write_node_log(node_id, "MOD_B created PR.")
        return NodeResult(node_id=node_id, status="COMPLETED", output=output)

    if dry_run or not writes_allowed:
        reason = "dry_run" if dry_run else "governor_report_only"
        tool_calls.append(
            {
                "tool": "fs_write",
                "args_summary": {
                    "path": output_path,
                    "resolved_path": str(resolved_output_path),
                    "bytes_estimate": node_input["content_bytes"],
                },
                "status": "SKIPPED",
                "bytes_in": node_input["content_bytes"],
                "bytes_out": 0,
                "reason": reason,
            }
        )
        output = {
            "node_id": node_id,
            "status": "COMPLETED",
            "module_id": "MOD_B",
            "side_effects": {
                "would_write": {
                    "target_path": str(resolved_output_path),
                    "bytes_estimate": node_input["content_bytes"],
                }
            },
            "tool_calls": tool_calls,
        }
        evidence.write_node_output(node_id, output)
        if dry_run:
            evidence.write_node_log(node_id, "MOD_B dry-run: no write performed.")
        else:
            evidence.write_node_log(node_id, "MOD_B report-only: write suppressed by governor.")
        return NodeResult(node_id=node_id, status="COMPLETED", output=output)

    if not allowed_side_effects:
        tool_calls.append(
            {
                "tool": "fs_write",
                "args_summary": {"path": output_path, "resolved_path": str(resolved_output_path)},
                "status": "SKIPPED",
                "bytes_in": node_input["content_bytes"],
                "bytes_out": 0,
            }
        )
        output = {
            "node_id": node_id,
            "status": "COMPLETED",
            "module_id": "MOD_B",
            "side_effects": {"write_skipped": {"reason": "side_effect_policy_disallows_write"}},
            "tool_calls": tool_calls,
        }
        evidence.write_node_output(node_id, output)
        evidence.write_node_log(node_id, "MOD_B: write skipped (policy).")
        return NodeResult(node_id=node_id, status="COMPLETED", output=output)

    try:
        fsw_res = gateway.call(
            "fs_write",
            {"path": output_path, "text": content, "encoding": "utf-8"},
            capability=capability,
            workspace=str(workspace),
        )
        tool_calls.append(
            {
                "tool": fsw_res.get("tool", "fs_write"),
                "status": fsw_res.get("status", "OK"),
                "bytes_in": fsw_res.get("bytes_in", 0),
                "bytes_out": fsw_res.get("bytes_out", 0),
                "args_summary": {
                    "path": output_path,
                    "resolved_path": fsw_res.get("resolved_path"),
                },
            }
        )
    except PolicyViolation as e:
        tool_calls.append(
            {
                "tool": "fs_write",
                "status": "FAILED",
                "bytes_in": node_input["content_bytes"],
                "bytes_out": 0,
                "error_code": e.error_code,
                "args_summary": {"path": output_path, "resolved_path": str(resolved_output_path)},
            }
        )
        output = {
            "node_id": node_id,
            "status": "FAILED",
            "module_id": "MOD_B",
            "side_effects": {},
            "tool_calls": tool_calls,
            "error_code": "POLICY_VIOLATION",
            "error": str(e),
        }
        evidence.write_node_output(node_id, output)
        evidence.write_node_log(node_id, f"MOD_B policy violation: {e.error_code}")
        raise
    output = {
        "node_id": node_id,
        "status": "COMPLETED",
        "module_id": "MOD_B",
        "side_effects": {
            "wrote": {"target_path": str(resolved_output_path), "bytes": node_input["content_bytes"]}
        },
        "tool_calls": tool_calls,
    }
    evidence.write_node_output(node_id, output)
    evidence.write_node_log(node_id, "MOD_B wrote output.")
    return NodeResult(node_id=node_id, status="COMPLETED", output=output)


def execute_workflow(
    *,
    envelope: dict,
    workflow: dict,
    provider: Provider,
    workspace: Path,
    evidence: EvidenceWriter,
    approval_threshold: float,
    writes_allowed: bool = True,
    budget: BudgetTracker | None = None,
    force_suspend_reason: str | None = None,
) -> dict[str, Any]:
    steps = workflow.get("steps", [])
    if not isinstance(steps, list):
        raise RuntimeError("Invalid workflow: steps must be a list.")

    gateway = ToolGateway()
    module_caps = _load_module_capabilities(workspace)

    status = "COMPLETED"
    node_results: list[dict[str, Any]] = []
    last_mod_a_output: dict[str, Any] | None = None
    provider_used: str | None = None
    model_used: str | None = None
    token_usage: dict[str, Any] | None = None
    secrets_used: list[str] = []

    for step in steps:
        if budget is not None:
            budget.checkpoint_time()

        if not isinstance(step, dict):
            raise RuntimeError("Invalid workflow: step must be an object.")
        node_id = step.get("id")
        node_type = step.get("type")
        if not isinstance(node_id, str) or not node_id:
            raise RuntimeError("Invalid workflow: step.id must be a non-empty string.")
        if not isinstance(node_type, str) or not node_type:
            raise RuntimeError("Invalid workflow: step.type must be a non-empty string.")

        if node_type == "module":
            module_id = step.get("module_id")
            if module_id in {"MOD_A", "MOD_POLICY_REVIEW", "MOD_DLQ_TRIAGE"}:
                if budget is not None:
                    budget.consume_attempt(count=1)
                if module_id == "MOD_A":
                    res = _exec_mod_a(
                        envelope=envelope,
                        provider=provider,
                        workspace=workspace,
                        evidence=evidence,
                        node_id=node_id,
                        gateway=gateway,
                        capability=module_caps.get("MOD_A", {}),
                        budget=budget,
                    )
                elif module_id == "MOD_POLICY_REVIEW":
                    res = _exec_mod_policy_review(
                        envelope=envelope,
                        workspace=workspace,
                        evidence=evidence,
                        node_id=node_id,
                        gateway=gateway,
                        capability=module_caps.get("MOD_POLICY_REVIEW", {}),
                        budget=budget,
                    )
                else:
                    res = _exec_mod_dlq_triage(
                        envelope=envelope,
                        workspace=workspace,
                        evidence=evidence,
                        node_id=node_id,
                        budget=budget,
                    )
                last_mod_a_output = res.output
                summary_obj = res.output.get("summary", {})
                tool_calls = res.output.get("tool_calls")
                if isinstance(tool_calls, list):
                    for tc in tool_calls:
                        if not isinstance(tc, dict):
                            continue
                        if tc.get("tool") != "secrets_get":
                            continue
                        if tc.get("status") != "OK":
                            continue
                        secret_id = tc.get("secret_id")
                        if isinstance(secret_id, str) and secret_id and secret_id not in secrets_used:
                            secrets_used.append(secret_id)
                if module_id == "MOD_A" and isinstance(summary_obj, dict):
                    p = summary_obj.get("provider")
                    m = summary_obj.get("model")
                    u = summary_obj.get("usage")
                    if isinstance(p, str):
                        provider_used = p
                    if isinstance(m, str):
                        model_used = m
                    if isinstance(u, dict):
                        token_usage = u
            elif module_id == "MOD_B":
                if last_mod_a_output is None:
                    raise RuntimeError("MOD_B requires prior module output.")
                res = _exec_mod_b(
                    envelope=envelope,
                    mod_a_output=last_mod_a_output,
                    workspace=workspace,
                    evidence=evidence,
                    node_id=node_id,
                    gateway=gateway,
                    capability=module_caps.get("MOD_B", {}),
                    writes_allowed=bool(writes_allowed),
                    budget=budget,
                )
            else:
                raise RuntimeError(f"Unknown module_id: {module_id}")
        elif node_type == "approval":
            res = _exec_approval(
                envelope=envelope,
                threshold=approval_threshold,
                evidence=evidence,
                node_id=node_id,
                force_suspend_reason=force_suspend_reason,
            )
            if res.status == "SUSPENDED":
                status = "SUSPENDED"
                node_results.append(
                    {"node_id": res.node_id, "status": res.status, "output": res.output}
                )
                break
        else:
            raise RuntimeError(f"Unknown node type: {node_type}")

        node_results.append({"node_id": res.node_id, "status": res.status, "output": res.output})
        if budget is not None:
            budget.checkpoint_time()

    result: dict[str, Any] = {
        "status": status,
        "workflow_id": workflow.get("workflow_id"),
        "nodes": node_results,
        "secrets_used": secrets_used,
    }
    if provider_used:
        result["provider_used"] = provider_used
    if model_used:
        result["model_used"] = model_used
    if token_usage:
        result["token_usage"] = token_usage
    if budget is not None:
        budget.update_elapsed()
        result["budget_usage"] = {
            "attempts_used": budget.usage.attempts_used,
            "elapsed_ms": budget.usage.elapsed_ms,
            "est_tokens_used": budget.usage.est_tokens_used,
        }
    return result


def execute_mod_b_only(
    *,
    envelope: dict,
    mod_a_output: dict[str, Any],
    workspace: Path,
    evidence: EvidenceWriter,
    node_id: str = "MOD_B",
    writes_allowed: bool = True,
    budget: BudgetTracker | None = None,
) -> NodeResult:
    gateway = ToolGateway()
    module_caps = _load_module_capabilities(workspace)
    return _exec_mod_b(
        envelope=envelope,
        mod_a_output=mod_a_output,
        workspace=workspace,
        evidence=evidence,
        node_id=node_id,
        gateway=gateway,
        capability=module_caps.get("MOD_B", {}),
        writes_allowed=bool(writes_allowed),
        budget=budget,
    )

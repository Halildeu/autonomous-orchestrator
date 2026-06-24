from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any

from src.evidence.writer import EvidenceWriter
from src.orchestrator.workflow_exec_contracts import NodeResult
from src.tools.gateway import PolicyViolation, ToolGateway, resolve_path_in_workspace
from src.utils.budget import estimate_tokens
from src.orchestrator.workflow_exec_steps import _render_summary_markdown

def _exec_mod_b_impl(
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

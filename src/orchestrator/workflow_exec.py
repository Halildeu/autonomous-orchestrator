from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from src.evidence.writer import EvidenceWriter
from src.providers.provider import Provider


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def read_approval_threshold(decision_policy_path: Path, *, default: float = 0.7) -> float:
    if not decision_policy_path.exists():
        return default
    try:
        import json

        raw = json.loads(decision_policy_path.read_text(encoding="utf-8"))
    except Exception:
        return default

    v = raw.get("approval_risk_threshold", default)
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f < 0 or f > 1:
        return default
    return f


@dataclass(frozen=True)
class NodeResult:
    node_id: str
    status: str  # COMPLETED | SUSPENDED | SKIPPED | FAILED
    output: dict[str, Any]


def _exec_mod_a(
    *,
    envelope: dict,
    provider: Provider,
    workspace: Path,
    evidence: EvidenceWriter,
    node_id: str,
) -> NodeResult:
    context = envelope.get("context") if isinstance(envelope.get("context"), dict) else {}
    input_path_raw = context.get("input_path")
    if isinstance(input_path_raw, str) and input_path_raw.strip():
        input_path = Path(input_path_raw)
    else:
        input_path = Path("fixtures/sample.md")

    resolved_input_path = (workspace / input_path).resolve() if not input_path.is_absolute() else input_path.resolve()
    if not _is_within(resolved_input_path, workspace):
        raise RuntimeError(f"Input path must be within workspace: {resolved_input_path}")
    if not resolved_input_path.exists():
        raise RuntimeError(f"Missing input markdown: {resolved_input_path}")

    markdown = resolved_input_path.read_text(encoding="utf-8")
    markdown_sha = sha256(markdown.encode("utf-8")).hexdigest()

    node_input = {
        "node_id": node_id,
        "module_id": "MOD_A",
        "resolved_input_path": str(resolved_input_path),
        "markdown_sha256": markdown_sha,
        "markdown_bytes": len(markdown.encode("utf-8")),
    }
    evidence.write_node_input(node_id, node_input)

    try:
        summary_obj = provider.summarize_markdown_to_json(markdown)
    except Exception as e:
        from src.providers.openai_provider import DeterministicStubProvider

        stub = DeterministicStubProvider()
        summary_obj = stub.summarize_markdown_to_json(markdown)
        summary_obj["provider_error"] = str(e)

    output = {
        "node_id": node_id,
        "status": "COMPLETED",
        "module_id": "MOD_A",
        "side_effects": {},
        "summary": summary_obj,
    }
    evidence.write_node_output(node_id, output)
    evidence.write_node_log(node_id, "MOD_A completed.")
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
) -> NodeResult:
    risk_score = envelope.get("risk_score", 0)
    try:
        risk = float(risk_score)
    except (TypeError, ValueError):
        risk = 0.0

    node_input = {"node_id": node_id, "risk_score": risk, "threshold": threshold}
    evidence.write_node_input(node_id, node_input)

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
) -> NodeResult:
    context = envelope.get("context") if isinstance(envelope.get("context"), dict) else {}
    output_path_raw = context.get("output_path")
    if isinstance(output_path_raw, str) and output_path_raw.strip():
        output_path = Path(output_path_raw)
    else:
        output_path = Path("fixtures/out.md")

    resolved_output_path = (
        (workspace / output_path).resolve() if not output_path.is_absolute() else output_path.resolve()
    )
    if not _is_within(resolved_output_path, workspace):
        raise RuntimeError(f"Output path must be within workspace: {resolved_output_path}")

    dry_run = bool(envelope.get("dry_run", False))
    side_effect_policy = envelope.get("side_effect_policy", "none")
    allowed_side_effects = side_effect_policy in ("draft", "allow")

    content = _render_summary_markdown(mod_a_output)
    node_input = {
        "node_id": node_id,
        "module_id": "MOD_B",
        "dry_run": dry_run,
        "side_effect_policy": side_effect_policy,
        "allowed_side_effects": allowed_side_effects,
        "resolved_output_path": str(resolved_output_path),
        "content_sha256": sha256(content.encode("utf-8")).hexdigest(),
        "content_bytes": len(content.encode("utf-8")),
    }
    evidence.write_node_input(node_id, node_input)

    if dry_run:
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
        }
        evidence.write_node_output(node_id, output)
        evidence.write_node_log(node_id, "MOD_B dry-run: no write performed.")
        return NodeResult(node_id=node_id, status="COMPLETED", output=output)

    if not allowed_side_effects:
        output = {
            "node_id": node_id,
            "status": "COMPLETED",
            "module_id": "MOD_B",
            "side_effects": {"write_skipped": {"reason": "side_effect_policy_disallows_write"}},
        }
        evidence.write_node_output(node_id, output)
        evidence.write_node_log(node_id, "MOD_B: write skipped (policy).")
        return NodeResult(node_id=node_id, status="COMPLETED", output=output)

    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_path.write_text(content, encoding="utf-8")
    output = {
        "node_id": node_id,
        "status": "COMPLETED",
        "module_id": "MOD_B",
        "side_effects": {
            "wrote": {"target_path": str(resolved_output_path), "bytes": node_input["content_bytes"]}
        },
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
) -> dict[str, Any]:
    steps = workflow.get("steps", [])
    if not isinstance(steps, list):
        raise RuntimeError("Invalid workflow: steps must be a list.")

    status = "COMPLETED"
    node_results: list[dict[str, Any]] = []
    last_mod_a_output: dict[str, Any] | None = None
    provider_used: str | None = None
    model_used: str | None = None
    token_usage: dict[str, Any] | None = None

    for step in steps:
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
            if module_id == "MOD_A":
                res = _exec_mod_a(
                    envelope=envelope, provider=provider, workspace=workspace, evidence=evidence, node_id=node_id
                )
                last_mod_a_output = res.output
                summary_obj = res.output.get("summary", {})
                if isinstance(summary_obj, dict):
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
                    raise RuntimeError("MOD_B requires MOD_A output.")
                res = _exec_mod_b(
                    envelope=envelope,
                    mod_a_output=last_mod_a_output,
                    workspace=workspace,
                    evidence=evidence,
                    node_id=node_id,
                )
            else:
                raise RuntimeError(f"Unknown module_id: {module_id}")
        elif node_type == "approval":
            res = _exec_approval(
                envelope=envelope, threshold=approval_threshold, evidence=evidence, node_id=node_id
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

    result: dict[str, Any] = {
        "status": status,
        "workflow_id": workflow.get("workflow_id"),
        "nodes": node_results,
    }
    if provider_used:
        result["provider_used"] = provider_used
    if model_used:
        result["model_used"] = model_used
    if token_usage:
        result["token_usage"] = token_usage
    return result


def execute_mod_b_only(
    *,
    envelope: dict,
    mod_a_output: dict[str, Any],
    workspace: Path,
    evidence: EvidenceWriter,
    node_id: str = "MOD_B",
) -> NodeResult:
    return _exec_mod_b(
        envelope=envelope,
        mod_a_output=mod_a_output,
        workspace=workspace,
        evidence=evidence,
        node_id=node_id,
    )

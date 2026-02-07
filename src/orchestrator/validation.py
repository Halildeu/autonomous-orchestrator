from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from src.utils.jsonio import load_json, to_canonical_json


_NODE_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,64}$")


def schema_errors(instance: Any, schema_path: Path) -> list[dict[str, str]]:
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: e.json_path)
    return [{"path": e.json_path or "$", "message": e.message} for e in errors]


def validate_envelope(envelope: Any, *, schema_path: Path, envelope_path: Path) -> None:
    if not schema_path.exists():
        raise RuntimeError(f"Missing envelope schema: {schema_path}")

    if not isinstance(envelope, dict):
        raise RuntimeError("Envelope must be a JSON object.")

    errors = schema_errors(envelope, schema_path)
    if errors:
        raise ValueError(
            json.dumps(
                {
                    "envelope_path": str(envelope_path),
                    "schema_path": str(schema_path),
                    "errors": errors[:10],
                },
                ensure_ascii=False,
            )
        )


def validate_strategy_table_intents(strategy_path: Path, *, intent_registry_schema_path: Path) -> None:
    if not intent_registry_schema_path.exists():
        return

    raw = load_json(strategy_path)
    derived = {"version": raw.get("version"), "intents": raw.get("routes", [])}
    errors = schema_errors(derived, intent_registry_schema_path)
    if errors:
        raise ValueError(
            json.dumps(
                {
                    "strategy_table_path": str(strategy_path),
                    "schema_path": str(intent_registry_schema_path),
                    "errors": errors[:10],
                },
                ensure_ascii=False,
            )
        )


def validate_workflow(workflow: Any, *, workflow_path: Path) -> None:
    errors: list[dict[str, str]] = []

    if not isinstance(workflow, dict):
        errors.append({"path": "$", "message": "Workflow must be a JSON object."})
    else:
        if not isinstance(workflow.get("version"), str) or not workflow.get("version"):
            errors.append({"path": "$.version", "message": "Workflow must include non-empty version."})
        if not isinstance(workflow.get("workflow_id"), str) or not workflow.get("workflow_id"):
            errors.append({"path": "$.workflow_id", "message": "Workflow must include non-empty workflow_id."})

        steps = workflow.get("steps")
        if not isinstance(steps, list) or not steps:
            errors.append({"path": "$.steps", "message": "Workflow must include non-empty steps list."})
        else:
            seen_ids: set[str] = set()
            for idx, step in enumerate(steps):
                pfx = f"$.steps[{idx}]"
                if not isinstance(step, dict):
                    errors.append({"path": pfx, "message": "Step must be an object."})
                    continue

                node_id = step.get("id")
                node_type = step.get("type")

                if not isinstance(node_id, str) or not node_id:
                    errors.append({"path": f"{pfx}.id", "message": "Step.id must be a non-empty string."})
                else:
                    if not _NODE_ID_RE.match(node_id):
                        errors.append(
                            {
                                "path": f"{pfx}.id",
                                "message": "Step.id must match ^[A-Z][A-Z0-9_]{2,64}$ (UPPER_SNAKE_CASE).",
                            }
                        )
                    if node_id in seen_ids:
                        errors.append({"path": f"{pfx}.id", "message": f"Duplicate step id: {node_id}"})
                    seen_ids.add(node_id)

                if not isinstance(node_type, str) or not node_type:
                    errors.append({"path": f"{pfx}.type", "message": "Step.type must be a non-empty string."})
                elif node_type == "module":
                    module_id = step.get("module_id")
                    if not isinstance(module_id, str) or not module_id:
                        errors.append({"path": f"{pfx}.module_id", "message": "Module step requires non-empty module_id."})
                    elif module_id not in {"MOD_A", "MOD_B", "MOD_POLICY_REVIEW", "MOD_DLQ_TRIAGE"}:
                        errors.append({"path": f"{pfx}.module_id", "message": f"Unsupported module_id: {module_id}"})
                elif node_type == "approval":
                    pass
                else:
                    errors.append({"path": f"{pfx}.type", "message": f"Unsupported step.type: {node_type}"})

    if errors:
        raise ValueError(
            json.dumps(
                {
                    "workflow_path": str(workflow_path),
                    "errors": errors[:10],
                },
                ensure_ascii=False,
            )
        )


def load_workflow_by_id(workspace: Path, workflow_id: str) -> tuple[Path, dict[str, Any]]:
    workflows_dir = workspace / "workflows"
    if not workflows_dir.exists():
        raise RuntimeError("Missing workflows/ directory.")

    matches: list[tuple[Path, dict[str, Any]]] = []
    for wf_path in sorted(workflows_dir.glob("*.json")):
        try:
            wf = load_json(wf_path)
        except Exception:
            continue
        if wf.get("workflow_id") == workflow_id:
            matches.append((wf_path, wf))

    if not matches:
        raise RuntimeError(f"Workflow not found for workflow_id={workflow_id}")
    if len(matches) > 1:
        raise RuntimeError(f"Multiple workflow files match workflow_id={workflow_id}: {[str(p) for p, _ in matches]}")
    return matches[0]


def workflow_fingerprint(workflow: dict[str, Any], workflow_path: Path) -> str:
    version = workflow.get("version")
    if isinstance(version, str) and version.strip():
        return version.strip()

    try:
        raw = workflow_path.read_bytes()
    except Exception:
        raw = to_canonical_json(workflow).encode("utf-8")
    return sha256(raw).hexdigest()

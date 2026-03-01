from __future__ import annotations

import json

from src.orchestrator import dlq, validation
from src.orchestrator.runner_stages.context import StageContext
from src.orchestrator.runner_utils import print_error


def validate_envelope_stage(*, stage_ctx: StageContext) -> None:
    envelope_schema_path = stage_ctx.workspace / "schemas" / "request-envelope.schema.json"
    try:
        validation.validate_envelope(
            stage_ctx.envelope,
            schema_path=envelope_schema_path,
            envelope_path=stage_ctx.envelope_path,
        )
    except ValueError as e:
        details = json.loads(str(e))
        errors = details.get("errors", [])
        budget_only = (
            isinstance(errors, list)
            and errors
            and all(isinstance(err, dict) and str(err.get("path", "")).startswith("$.budget") for err in errors)
        )
        if budget_only:
            dlq_path = dlq.write_dlq_record(
                workspace=stage_ctx.workspace,
                stage="BUDGET",
                error_code="BUDGET_INVALID",
                message="Budget failed schema validation.",
                envelope=stage_ctx.envelope,
            )
            print_error(
                "BUDGET_INVALID",
                "Budget failed schema validation.",
                details={
                    "envelope_path": str(stage_ctx.envelope_path),
                    "errors": errors[:10],
                    "dlq_file": dlq_path.name,
                    "result_state": "FAILED",
                },
            )
            raise SystemExit(2)

        dlq.write_dlq_record(
            workspace=stage_ctx.workspace,
            stage="ENVELOPE_VALIDATE",
            error_code="SCHEMA_INVALID",
            message="Envelope failed schema validation.",
            envelope=stage_ctx.envelope,
        )
        print_error("INVALID_ENVELOPE_SCHEMA", "Envelope failed schema validation.", details=details)
        raise SystemExit(2)
    except Exception as e:
        dlq.write_dlq_record(
            workspace=stage_ctx.workspace,
            stage="ENVELOPE_VALIDATE",
            error_code="SCHEMA_INVALID",
            message="Envelope schema validation could not be performed.",
            envelope=stage_ctx.envelope,
        )
        print_error(
            "INVALID_ENVELOPE_SCHEMA",
            "Envelope schema validation could not be performed.",
            details={
                "envelope_path": str(stage_ctx.envelope_path),
                "schema_path": str(envelope_schema_path),
                "error": str(e),
            },
        )
        raise SystemExit(2)

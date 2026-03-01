from __future__ import annotations

from dataclasses import dataclass
import json
from hashlib import sha256

from src.orchestrator import idempotency
from src.orchestrator.runner_context import RunContext
from src.orchestrator.runner_stages.context import StageContext
from src.orchestrator.runner_utils import replay_forced_run_id


@dataclass
class IdempotencyState:
    run_id: str
    idempotency_key_hash: str | None


def idempotency_stage(
    *,
    stage_ctx: StageContext,
    run_ctx: RunContext,
    workflow_fingerprint: str,
    approval_threshold_used: float,
) -> IdempotencyState | None:
    idempotency_key_hash: str | None = None
    store_key_id: str | None = None

    tenant_id_raw = stage_ctx.envelope.get("tenant_id")
    if (
        isinstance(tenant_id_raw, str)
        and tenant_id_raw
        and isinstance(run_ctx.idempotency_key, str)
        and run_ctx.idempotency_key
    ):
        key_plain = f"{tenant_id_raw}:{run_ctx.idempotency_key}:{run_ctx.workflow_id}"
        idempotency_key_hash = sha256(key_plain.encode("utf-8")).hexdigest()
        if stage_ctx.replay_force_new_run:
            run_id = replay_forced_run_id(replay_of=stage_ctx.replay_of or run_ctx.request_id or "unknown")
        elif stage_ctx.force_new_run:
            # Envelope runs: force a new run_id without touching idempotency mappings.
            run_id = idempotency.timestamp_run_id()
        else:
            store_key_id = idempotency_key_hash[:24]
            run_id = idempotency.deterministic_run_id(
                tenant_id=tenant_id_raw,
                idempotency_key=run_ctx.idempotency_key,
                workflow_id=run_ctx.workflow_id,
                workflow_fingerprint=workflow_fingerprint,
            )
    else:
        run_id = (
            replay_forced_run_id(replay_of=stage_ctx.replay_of or run_ctx.request_id or "unknown")
            if stage_ctx.replay_force_new_run
            else idempotency.timestamp_run_id()
        )

    store_path = stage_ctx.workspace / ".cache" / "idempotency_store.v1.json"
    mappings, migrated = idempotency.load_idempotency_store(store_path)
    changed = migrated
    if store_key_id:
        if mappings.get(store_key_id) != run_id:
            mappings[store_key_id] = run_id
            changed = True
        if changed or not store_path.exists():
            idempotency.save_idempotency_store(store_path, mappings)

        summary_path = stage_ctx.out_dir / run_id / "summary.json"
        if idempotency.read_result_state(summary_path) == "COMPLETED":
            payload = {
                "status": "IDEMPOTENT_HIT",
                "message": "IDEMPOTENT_HIT",
                "run_id": run_id,
                "request_id": run_ctx.request_id,
                "tenant_id": run_ctx.tenant_id,
                "workflow_id": run_ctx.workflow_id,
                "workflow_fingerprint": workflow_fingerprint,
                "approval_threshold_used": approval_threshold_used,
                "idempotency_key_hash": idempotency_key_hash,
                "governor_mode_used": run_ctx.governor_mode_used,
                "governor_quarantine_hit": run_ctx.governor_quarantine_hit,
                "governor_concurrency_limit_hit": run_ctx.governor_concurrency_limit_hit,
            }
            if stage_ctx.replay_of is not None:
                payload["replay_of"] = stage_ctx.replay_of
                payload["replay_warnings"] = list(stage_ctx.replay_warnings)
            print(
                json.dumps(
                    payload,
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return None

    return IdempotencyState(run_id=run_id, idempotency_key_hash=idempotency_key_hash)

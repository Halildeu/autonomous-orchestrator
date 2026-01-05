from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.orchestrator import dlq
from src.orchestrator.runner_utils import print_error
from src.utils.jsonio import load_json


@dataclass
class ReplayContext:
    replay_of: str | None
    replay_provenance: dict[str, Any] | None
    replay_warnings: list[str]
    replay_force_new_run: bool
    force_new_run: bool


def load_envelope(
    *,
    args: Any,
    workspace: Path,
) -> tuple[dict[str, Any], Path, ReplayContext]:
    replay_of: str | None = None
    replay_provenance: dict[str, Any] | None = None
    replay_warnings: list[str] = []
    force_new_run = bool(getattr(args, "force_new_run", False))
    replay_force_new_run = force_new_run if getattr(args, "replay", None) else False

    if getattr(args, "replay", None):
        replay_in = Path(args.replay)
        replay_dir = (workspace / replay_in).resolve() if not replay_in.is_absolute() else replay_in.resolve()
        try:
            replay_dir.relative_to(workspace)
        except ValueError:
            print_error(
                "INVALID_REPLAY_PATH",
                "--replay must be within --workspace for safety.",
                details={"replay_dir": str(replay_dir), "workspace": str(workspace)},
            )
            raise SystemExit(2)

        replay_of = replay_dir.name
        envelope_path = replay_dir / "request.json"
        if not envelope_path.exists():
            print_error(
                "INVALID_REPLAY_EVIDENCE",
                "Replay evidence must contain request.json.",
                details={"request_path": str(envelope_path)},
            )
            raise SystemExit(2)

        try:
            envelope = load_json(envelope_path)
        except Exception as e:
            print_error(
                "INVALID_REPLAY_EVIDENCE",
                "Failed to load request.json from replay evidence directory.",
                details={"request_path": str(envelope_path), "error": str(e)},
            )
            raise SystemExit(2)

        prov_path = replay_dir / "provenance.v1.json"
        if prov_path.exists():
            try:
                prov = load_json(prov_path)
                if isinstance(prov, dict):
                    replay_provenance = prov
            except Exception:
                replay_provenance = None
    else:
        envelope_path_in = Path(args.envelope)
        envelope_path = (
            (workspace / envelope_path_in).resolve()
            if not envelope_path_in.is_absolute()
            else envelope_path_in.resolve()
        )

        try:
            envelope = load_json(envelope_path)
        except Exception as e:
            dlq.write_dlq_record(
                workspace=workspace,
                stage="ENVELOPE_VALIDATE",
                error_code="SCHEMA_INVALID",
                message="Failed to parse envelope JSON.",
                envelope={},
            )
            print_error(
                "INVALID_ENVELOPE_JSON",
                "Failed to parse envelope JSON.",
                details={"envelope_path": str(envelope_path), "error": str(e)},
            )
            raise SystemExit(2)

    ctx = ReplayContext(
        replay_of=replay_of,
        replay_provenance=replay_provenance,
        replay_warnings=replay_warnings,
        replay_force_new_run=replay_force_new_run,
        force_new_run=force_new_run,
    )
    return envelope, envelope_path, ctx

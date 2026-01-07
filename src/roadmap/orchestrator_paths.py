from __future__ import annotations

from pathlib import Path


def resolve_path(core_root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    return (core_root / path).resolve()


def finish_state_path(workspace_root: Path) -> Path:
    return (workspace_root / ".cache" / "roadmap_state.v1.json").resolve()


def finish_state_schema(core_root: Path) -> Path:
    return (core_root / "schemas" / "roadmap-state.schema.json").resolve()


def finish_evidence_root(core_root: Path) -> Path:
    return (core_root / "evidence" / "roadmap_finish").resolve()


def finish_run_dir(evidence_root: Path, run_id: str) -> Path:
    return (evidence_root / run_id).resolve()


def orchestrator_evidence_root(core_root: Path) -> Path:
    return (core_root / "evidence" / "roadmap_orchestrator").resolve()

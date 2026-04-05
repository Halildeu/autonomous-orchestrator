from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from src.ops.roadmap_cli import cmd_project_status, register_roadmap_subcommands
from src.ops.roadmap_cli_helpers import DEFAULT_CANONICAL_ROADMAP_REL
from src.ops import system_status_report as system_status_report_mod
from src.roadmap import orchestrator as roadmap_orchestrator


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def test_project_status_parser_defaults_to_canonical_roadmap(tmp_path: Path) -> None:
    workspace_root = tmp_path / "ws"
    workspace_root.mkdir(parents=True, exist_ok=True)

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_roadmap_subcommands(sub)
    args = parser.parse_args(
        [
            "project-status",
            "--workspace-root",
            str(workspace_root),
            "--mode",
            "json",
        ]
    )

    assert args.roadmap == DEFAULT_CANONICAL_ROADMAP_REL.as_posix()


def test_project_status_json_surfaces_canonical_evidence_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    workspace_root = tmp_path / "ws"
    workspace_root.mkdir(parents=True, exist_ok=True)

    system_status_path = workspace_root / ".cache" / "reports" / "system_status.v1.json"
    _write_json(system_status_path, {"overall_status": "WARN"})

    finish_report_path = workspace_root / ".cache" / "reports" / "finish_report.v1.json"
    _write_json(finish_report_path, {"status": "OK"})
    last_finish_hint = workspace_root / ".cache" / "last_finish_evidence.v1.txt"
    last_finish_hint.parent.mkdir(parents=True, exist_ok=True)
    last_finish_hint.write_text(".cache/reports/finish_report.v1.json\n", encoding="utf-8")

    state_path = workspace_root / ".cache" / "roadmap_state.v1.json"
    monkeypatch.setattr(
        roadmap_orchestrator,
        "status",
        lambda **_: {
            "status": "OK",
            "bootstrapped": True,
            "next_milestone": "M2",
            "completed_count": 7,
            "last_result": {"evidence_path": ".cache/reports/follow_run.v1.json"},
            "state_path": str(state_path.resolve()),
        },
    )

    rc = cmd_project_status(
        argparse.Namespace(
            workspace_root=str(workspace_root),
            mode="json",
        )
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    expected_roadmap = str((repo_root / DEFAULT_CANONICAL_ROADMAP_REL).resolve())
    expected_system_status = str(system_status_path.resolve())
    expected_finish_report = str(finish_report_path.resolve())

    assert payload["roadmap_path"] == expected_roadmap
    assert payload["completed_count"] == 7
    assert payload["evidence"] == [
        expected_roadmap,
        expected_finish_report,
        expected_system_status,
    ]


def test_run_system_status_returns_absolute_provenance_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_root = tmp_path / "ws"
    core_root = tmp_path / "repo"
    workspace_root.mkdir(parents=True, exist_ok=True)
    (core_root / "policies").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        system_status_report_mod,
        "build_system_status",
        lambda **_: {
            "version": "v1",
            "generated_at": "2026-04-05T00:00:00Z",
            "workspace_root": str(workspace_root.resolve()),
            "overall_status": "OK",
            "sections": {},
            "notes": [],
        },
    )
    monkeypatch.setattr(system_status_report_mod, "_validate_schema", lambda *_: [])
    monkeypatch.setattr(system_status_report_mod, "_render_md", lambda *_: "# stub\n")
    monkeypatch.setattr(
        system_status_report_mod,
        "build_drift_scoreboard",
        lambda **_: {"report_path": ".cache/reports/managed_repo_drift_scoreboard.v1.json"},
    )
    monkeypatch.setattr(
        system_status_report_mod,
        "write_drift_scoreboard",
        lambda **_: ".cache/reports/managed_repo_drift_scoreboard.v1.json",
    )

    result = system_status_report_mod.run_system_status(
        workspace_root=workspace_root,
        core_root=core_root,
        dry_run=False,
    )

    out_json = workspace_root / ".cache" / "reports" / "system_status.v1.json"
    out_md = workspace_root / ".cache" / "reports" / "system_status.v1.md"
    drift_path = workspace_root / ".cache" / "reports" / "managed_repo_drift_scoreboard.v1.json"

    assert result["status"] == "OK"
    assert result["out_json"] == str(out_json.resolve())
    assert result["out_md"] == str(out_md.resolve())
    assert result["drift_scoreboard_path"] == str(drift_path.resolve())

    source_artifact_paths = result.get("source_artifact_paths")
    assert isinstance(source_artifact_paths, dict)
    assert source_artifact_paths["portfolio_status"] == str(
        (workspace_root / ".cache" / "reports" / "portfolio_status.v1.json").resolve()
    )
    assert source_artifact_paths["system_status_json"] == str(out_json.resolve())
    assert source_artifact_paths["system_status_md"] == str(out_md.resolve())
    assert source_artifact_paths["drift_scoreboard"] == str(drift_path.resolve())

    report = json.loads(out_json.read_text(encoding="utf-8"))
    notes = report.get("notes")
    assert isinstance(notes, list)
    assert f"source_artifact.system_status_json={out_json.resolve()}" in notes
    assert f"source_artifact.drift_scoreboard={drift_path.resolve()}" in notes

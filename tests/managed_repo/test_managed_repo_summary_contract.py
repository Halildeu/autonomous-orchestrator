"""Contract tests for managed repo standards summary: absolute paths and origin fields."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.ops.managed_repo_standards import build_managed_repo_standards_summary


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _build_fixture(tmp: Path) -> dict:
    core_root = tmp / "core"
    workspace_root = core_root / ".cache" / "ws_customer_default"
    workspace_root.mkdir(parents=True, exist_ok=True)

    _write_json(
        workspace_root / ".cache" / "managed_repos.v1.json",
        {
            "version": "v1",
            "kind": "managed-repos-manifest",
            "repos": [
                {"repo_root": "/tmp/repo-alpha", "repo_slug": "org/repo-alpha", "domain_profile": "fullstack", "critical": True},
                {"repo_root": "/tmp/repo-beta", "repo_slug": "org/repo-beta", "domain_profile": "backend-api", "critical": False},
            ],
        },
    )

    _write_json(
        workspace_root / ".cache" / "reports" / "managed_repo_standards_sync" / "report.v1.json",
        {
            "version": "v1",
            "mode": "dry-run",
            "target_count": 2,
            "failed_count": 0,
            "results": [
                {
                    "repo_root": "/tmp/repo-alpha",
                    "status": "OK",
                    "changed_files": 1,
                    "files": [{"path": "standards.lock", "action": "would_update"}],
                },
                {
                    "repo_root": "/tmp/repo-beta",
                    "status": "OK",
                    "changed_files": 0,
                    "files": [{"path": "standards.lock", "action": "no_change"}],
                },
            ],
        },
    )

    return build_managed_repo_standards_summary(
        workspace_root=workspace_root,
        core_root=core_root,
        max_repos=10,
    )


def test_repo_root_is_absolute_path() -> None:
    with tempfile.TemporaryDirectory(prefix="mrs-abs-") as td:
        summary = _build_fixture(Path(td).resolve())
        repos = summary.get("repos", [])
        assert len(repos) == 2
        for repo in repos:
            root = repo.get("repo_root", "")
            assert root.startswith("/"), f"repo_root must be absolute, got: {root}"


def test_origin_field_present() -> None:
    with tempfile.TemporaryDirectory(prefix="mrs-origin-") as td:
        summary = _build_fixture(Path(td).resolve())
        repos = summary.get("repos", [])
        assert len(repos) == 2
        origins = {r["origin"] for r in repos}
        assert "org/repo-alpha" in origins
        assert "org/repo-beta" in origins


def test_domain_profile_field_present() -> None:
    with tempfile.TemporaryDirectory(prefix="mrs-dp-") as td:
        summary = _build_fixture(Path(td).resolve())
        repos = summary.get("repos", [])
        profiles = {r.get("repo_root", "").split("/")[-1]: r.get("domain_profile", "") for r in repos}
        assert profiles.get("repo-alpha") == "fullstack"
        assert profiles.get("repo-beta") == "backend-api"


def test_origin_empty_when_not_in_manifest() -> None:
    """When a repo appears in the sync report but not in the manifest, origin should be empty."""
    with tempfile.TemporaryDirectory(prefix="mrs-noorigin-") as td:
        tmp = Path(td).resolve()
        core_root = tmp / "core"
        workspace_root = core_root / ".cache" / "ws_customer_default"
        workspace_root.mkdir(parents=True, exist_ok=True)

        _write_json(
            workspace_root / ".cache" / "managed_repos.v1.json",
            {"version": "v1", "repos": []},
        )

        _write_json(
            workspace_root / ".cache" / "reports" / "managed_repo_standards_sync" / "report.v1.json",
            {
                "version": "v1",
                "mode": "dry-run",
                "target_count": 1,
                "results": [
                    {"repo_root": "/tmp/orphan-repo", "status": "OK", "changed_files": 0, "files": []},
                ],
            },
        )

        summary = build_managed_repo_standards_summary(
            workspace_root=workspace_root,
            core_root=core_root,
        )
        repos = summary.get("repos", [])
        assert len(repos) == 1
        assert repos[0]["origin"] == ""
        assert repos[0]["domain_profile"] == ""

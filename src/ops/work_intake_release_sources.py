from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _git_available(root: Path) -> bool:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return False
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def _git_dirty_tree(root: Path) -> bool | None:
    if not _git_available(root):
        return None
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return bool(proc.stdout.strip())


def _git_unpushed_commits(root: Path) -> int | None:
    if not _git_available(root):
        return None
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-list", "--left-right", "--count", "@{u}...HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    parts = proc.stdout.strip().split()
    if len(parts) != 2:
        return None
    try:
        behind, ahead = int(parts[0]), int(parts[1])
    except Exception:
        return None
    _ = behind
    return ahead


def _load_integrity_sources(workspace_root: Path, notes: list[str]) -> list[dict[str, Any]]:
    report_path = workspace_root / ".cache" / "reports" / "integrity_verify.v1.json"
    if not report_path.exists():
        notes.append("integrity_report_missing")
        return []
    try:
        obj = _load_json(report_path)
    except Exception:
        notes.append("integrity_report_invalid")
        return []
    status = obj.get("status") if isinstance(obj, dict) else None
    status_str = str(status) if isinstance(status, str) else ""
    if status_str != "FAIL":
        return []
    evidence = [str(Path(".cache") / "reports" / "integrity_verify.v1.json")]
    return [
        {
            "source_type": "INTEGRITY",
            "source_ref": "integrity_fail",
            "title": "Integrity verify FAIL",
            "integrity_status": status_str,
            "evidence_paths": evidence,
        }
    ]


def _release_source(
    *,
    signal: str,
    title: str,
    evidence: list[str],
    channel: str,
    release_status: str | None,
    dirty_tree: bool | None,
    unpushed_commits: int | None,
    publish_blocked: bool | None,
    plan_present: bool | None,
) -> dict[str, Any]:
    source: dict[str, Any] = {
        "source_type": "RELEASE",
        "source_ref": f"release:{signal}",
        "title": title,
        "release_signal": signal,
        "release_channel": channel,
        "evidence_paths": evidence,
    }
    if release_status is not None:
        source["release_status"] = release_status
    if dirty_tree is not None:
        source["release_dirty_tree"] = dirty_tree
    if unpushed_commits is not None:
        source["release_unpushed_commits"] = unpushed_commits
    if publish_blocked is not None:
        source["release_publish_blocked"] = publish_blocked
    if plan_present is not None:
        source["release_plan_present"] = plan_present
    return source


def _load_release_sources(workspace_root: Path, notes: list[str]) -> list[dict[str, Any]]:
    plan_rel = str(Path(".cache") / "reports" / "release_plan.v1.json")
    manifest_rel = str(Path(".cache") / "reports" / "release_manifest.v1.json")
    notes_rel = str(Path(".cache") / "reports" / "release_notes.v1.md")
    plan_path = workspace_root / plan_rel
    manifest_path = workspace_root / manifest_rel
    notes_path = workspace_root / notes_rel

    evidence: list[str] = []
    channel = "rc"
    release_status: str | None = None
    dirty_tree: bool | None = None
    unpushed_commits: int | None = None
    publish_blocked: bool | None = None
    plan_present: bool | None = None
    plan_seed = False
    manifest_seed = False

    if plan_path.exists():
        try:
            plan = _load_json(plan_path)
        except Exception:
            notes.append("release_plan_invalid")
            plan = None
        else:
            evidence.append(plan_rel)
            if isinstance(plan, dict):
                channel = str(plan.get("channel") or channel)
                plan_seed = bool(plan.get("seed"))
                if not plan_seed:
                    plan_present = True
                    dirty_tree = bool(plan.get("dirty_tree", False))
                    release_status = str(plan.get("status") or "")
    else:
        notes.append("release_plan_missing")

    if manifest_path.exists():
        try:
            manifest = _load_json(manifest_path)
        except Exception:
            notes.append("release_manifest_invalid")
            manifest = None
        else:
            evidence.append(manifest_rel)
            if isinstance(manifest, dict):
                channel = str(manifest.get("channel") or channel)
                manifest_seed = bool(manifest.get("seed"))
                if not manifest_seed:
                    dirty_tree = bool(manifest.get("dirty_tree", dirty_tree or False))
                    publish_blocked = not bool(manifest.get("publish_allowed", False))
                    release_status = str(manifest.get("status") or release_status or "")
    else:
        notes.append("release_manifest_missing")

    if notes_path.exists():
        evidence.append(notes_rel)

    seeded_release = plan_seed or manifest_seed
    repo_root = _find_repo_root(Path(__file__).resolve())
    if dirty_tree is None:
        dirty_tree = False if seeded_release else _git_dirty_tree(repo_root)
    unpushed_commits = 0 if seeded_release else _git_unpushed_commits(repo_root)

    sources: list[dict[str, Any]] = []
    if plan_present:
        sources.append(
            _release_source(
                signal="plan_present",
                title="Release plan present",
                evidence=evidence,
                channel=channel,
                release_status=None,
                dirty_tree=None,
                unpushed_commits=None,
                publish_blocked=None,
                plan_present=True,
            )
        )
    if release_status == "WARN":
        sources.append(
            _release_source(
                signal="status_warn",
                title="Release status WARN",
                evidence=evidence,
                channel=channel,
                release_status="WARN",
                dirty_tree=None,
                unpushed_commits=None,
                publish_blocked=None,
                plan_present=None,
            )
        )
    if release_status == "FAIL":
        sources.append(
            _release_source(
                signal="status_fail",
                title="Release status FAIL",
                evidence=evidence,
                channel=channel,
                release_status="FAIL",
                dirty_tree=None,
                unpushed_commits=None,
                publish_blocked=None,
                plan_present=None,
            )
        )
    if dirty_tree is True:
        sources.append(
            _release_source(
                signal="dirty_tree",
                title="Release dirty tree",
                evidence=evidence,
                channel=channel,
                release_status=None,
                dirty_tree=True,
                unpushed_commits=None,
                publish_blocked=None,
                plan_present=None,
            )
        )
    if isinstance(unpushed_commits, int) and unpushed_commits > 0:
        sources.append(
            _release_source(
                signal="unpushed_commits",
                title="Release unpushed commits",
                evidence=evidence,
                channel=channel,
                release_status=None,
                dirty_tree=None,
                unpushed_commits=unpushed_commits,
                publish_blocked=None,
                plan_present=None,
            )
        )
    if publish_blocked is True:
        sources.append(
            _release_source(
                signal="publish_blocked",
                title="Release publish blocked",
                evidence=evidence,
                channel=channel,
                release_status=None,
                dirty_tree=None,
                unpushed_commits=None,
                publish_blocked=True,
                plan_present=None,
            )
        )

    return sources

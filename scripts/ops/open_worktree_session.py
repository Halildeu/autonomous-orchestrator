#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def _canonical_root() -> Path:
    """Resolve canonical repo root via git-common-dir so worktrees share state."""
    try:
        common = subprocess.check_output(
            ["git", "rev-parse", "--git-common-dir"], cwd=str(ROOT), text=True
        ).strip()
        common_path = Path(common)
        if not common_path.is_absolute():
            common_path = (ROOT / common_path).resolve()
        return common_path.parent.resolve()
    except Exception:
        return ROOT


CANONICAL_ROOT = _canonical_root()
# Registry is runtime coordination state — shared across worktrees via canonical
# tree, untracked. Legacy path kept as fallback for migration window.
DEFAULT_REGISTRY = CANONICAL_ROOT / ".worktree-registry.json"
DEFAULT_OUT = ROOT / ".cache" / "reports" / "worktree_open_session.v1.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_git(args: list[str], *, cwd: Path | None = None) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd or ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or f"git {' '.join(args)} failed").strip())
    return proc.stdout


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse_worktree_list() -> list[dict[str, Any]]:
    raw = _run_git(["worktree", "list", "--porcelain"])
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    for line in raw.splitlines():
        if not line.strip():
            if current:
                entries.append(current)
                current = {}
            continue
        if line.startswith("worktree "):
            current["path"] = line.split(" ", 1)[1].strip()
        elif line.startswith("HEAD "):
            current["head"] = line.split(" ", 1)[1].strip()
        elif line.startswith("branch "):
            ref = line.split(" ", 1)[1].strip()
            current["branch_ref"] = ref
            current["branch"] = ref.removeprefix("refs/heads/")
    if current:
        entries.append(current)
    return entries


def _dirty_count(path: Path) -> int:
    return len([line for line in _run_git(["status", "--short"], cwd=path).splitlines() if line.strip()])


def _ensure_registry_exists(path: Path) -> dict[str, Any]:
    if path.exists():
        return _load_json(path)
    payload = {
        "version": "v1",
        "generated_at": _now_iso(),
        "repo_root": str(ROOT),
        "canonical_worktree_path": str(ROOT),
        "entries": [
            {
                "path": str(ROOT),
                "branch": _run_git(["branch", "--show-current"]).strip(),
                "head": _run_git(["rev-parse", "HEAD"]).strip(),
                "kind": "canonical",
                "status": "ACTIVE",
                "owner": "system",
                "purpose": "primary_managed_repo_line",
                "intake_id": "",
                "read_only": False,
                "allowed_paths": ["**"],
                "opened_at": _now_iso(),
                "expires_at": "",
                "close_condition": "canonical_never_closed",
            }
        ],
        "notes": ["BOOTSTRAPPED_BY_OPEN_WORKTREE_SESSION=true"],
    }
    _write_json(path, payload)
    return payload


def _branch_exists(branch: str) -> bool:
    proc = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=str(ROOT),
    )
    return proc.returncode == 0


def _append_registry_entry(registry_path: Path, entry: dict[str, Any]) -> None:
    payload = _ensure_registry_exists(registry_path)
    entries = payload.get("entries") if isinstance(payload.get("entries"), list) else []
    entries = [item for item in entries if not (isinstance(item, dict) and str(item.get("path") or "") == entry["path"] and str(item.get("status") or "").upper() == "ACTIVE")]
    entries.append(entry)
    payload["entries"] = entries
    payload["generated_at"] = _now_iso()
    _write_json(registry_path, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Open a managed repo side worktree under intake-linked hygiene rules.")
    parser.add_argument("--path", required=True, help="New worktree path.")
    parser.add_argument("--branch", required=True, help="Branch to create/use (must start with codex/).")
    parser.add_argument("--purpose", required=True, help="Short purpose text.")
    parser.add_argument("--owner", required=True, help="Owner/chat tag.")
    parser.add_argument("--intake-id", required=True, help="Linked intake id.")
    parser.add_argument("--close-condition", required=True, help="Condition that closes this worktree.")
    parser.add_argument("--allowed-path", action="append", default=[], help="Allowed relative path glob (repeatable).")
    parser.add_argument("--ttl-hours", default="8", help="TTL in hours (default: 8).")
    parser.add_argument("--source-branch", default="", help="Source branch to branch from (default: current branch).")
    parser.add_argument("--read-only", action="store_true", help="Mark session as read-only.")
    parser.add_argument("--use-existing-branch", action="store_true", help="Attach to existing branch instead of creating a new one.")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY), help="Registry JSON path.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Report JSON path.")
    parser.add_argument("--apply", action="store_true", help="Actually create the worktree.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    target_path = Path(str(args.path)).expanduser().resolve()
    branch = str(args.branch).strip()
    source_branch = str(args.source_branch).strip() or _run_git(["branch", "--show-current"]).strip()
    registry_path = Path(str(args.registry)).expanduser().resolve()
    out_path = Path(str(args.out)).expanduser().resolve()

    report: dict[str, Any] = {
        "kind": "worktree-open-session",
        "version": "v1",
        "generated_at": _now_iso(),
        "repo_root": str(ROOT),
        "path": str(target_path),
        "branch": branch,
        "source_branch": source_branch,
        "status": "FAIL",
        "apply": bool(args.apply),
    }

    try:
        _allowed_branch_prefixes = (
            "codex/",
            "claude/",
            "feat/claude-",
            "fix/claude-",
            "feat/codex-",
            "fix/codex-",
        )
        if not any(branch.startswith(p) for p in _allowed_branch_prefixes):
            raise RuntimeError(
                "branch_prefix_invalid:must_start_with_one_of:"
                + "|".join(_allowed_branch_prefixes)
            )
        if target_path == ROOT:
            raise RuntimeError("target_path_is_canonical_repo_root")
        if target_path.exists():
            raise RuntimeError("target_path_already_exists")
        if _dirty_count(ROOT) > 0:
            raise RuntimeError("canonical_repo_dirty")

        worktrees = _parse_worktree_list()
        dirty_side_count = sum(
            1
            for item in worktrees
            if Path(str(item.get("path") or "")).resolve() != ROOT.resolve()
            and _dirty_count(Path(str(item.get("path") or "")).resolve()) > 0
        )
        if dirty_side_count > 0 and not args.read_only:
            raise RuntimeError("dirty_side_worktree_exists")
        if any(Path(str(item.get("path") or "")).resolve() == target_path for item in worktrees):
            raise RuntimeError("target_path_already_registered_as_worktree")

        branch_exists = _branch_exists(branch)
        if args.use_existing_branch and not branch_exists:
            raise RuntimeError("branch_missing_for_use_existing_branch")
        if not args.use_existing_branch and branch_exists:
            raise RuntimeError("branch_already_exists")

        ttl_hours = max(1, int(str(args.ttl_hours)))
        opened_at = datetime.now(timezone.utc).replace(microsecond=0)
        expires_at = opened_at + timedelta(hours=ttl_hours)
        entry = {
            "path": str(target_path),
            "branch": branch,
            "head": "",
            "kind": "side",
            "status": "ACTIVE",
            "owner": str(args.owner).strip(),
            "purpose": str(args.purpose).strip(),
            "intake_id": str(args.intake_id).strip(),
            "read_only": bool(args.read_only),
            "allowed_paths": [str(item).strip() for item in (args.allowed_path or []) if str(item).strip()],
            "opened_at": opened_at.isoformat().replace("+00:00", "Z"),
            "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
            "close_condition": str(args.close_condition).strip(),
        }
        report["entry"] = entry
        report["dirty_side_worktree_count_before"] = dirty_side_count

        if args.apply:
            if args.use_existing_branch:
                _run_git(["worktree", "add", str(target_path), branch])
            else:
                _run_git(["worktree", "add", "-b", branch, str(target_path), source_branch])
            entry["head"] = _run_git(["rev-parse", "HEAD"], cwd=target_path).strip()
            _append_registry_entry(registry_path, entry)
            report["status"] = "OK"
        else:
            report["status"] = "PLAN_ONLY"

    except Exception as exc:  # noqa: BLE001
        report["error"] = str(exc)

    _write_json(out_path, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] in {"OK", "PLAN_ONLY"} else 2


if __name__ == "__main__":
    raise SystemExit(main())

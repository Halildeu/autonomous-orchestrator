#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
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
DEFAULT_OUT = ROOT / ".cache" / "reports" / "worktree_reconciliation.v1.json"


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


def _parse_status_line(line: str) -> str:
    raw = line[3:] if len(line) >= 4 else line
    if " -> " in raw:
        return raw.split(" -> ", 1)[1].strip()
    return raw.strip()


def _dirty_paths(path: Path) -> list[str]:
    return [_parse_status_line(line) for line in _run_git(["status", "--short"], cwd=path).splitlines() if line.strip()]


def _update_registry_close(*, registry_path: Path, target_path: str, owner: str, reason: str, reconciliation_report: str) -> None:
    if not registry_path.exists():
        return
    payload = _load_json(registry_path)
    entries = payload.get("entries") if isinstance(payload.get("entries"), list) else []
    for item in entries:
        if not isinstance(item, dict):
            continue
        if str(item.get("path") or "") != target_path:
            continue
        if str(item.get("status") or "").upper() != "ACTIVE":
            continue
        item["status"] = "CLOSED"
        item["closed_at"] = _now_iso()
        item["closed_by"] = owner
        item["close_reason"] = reason
        item["reconciliation_report"] = reconciliation_report
    payload["generated_at"] = _now_iso()
    _write_json(registry_path, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Close a managed repo side worktree with reconciliation evidence.")
    parser.add_argument("--path", required=True, help="Worktree path to close.")
    parser.add_argument("--owner", required=True, help="Owner/chat tag closing the worktree.")
    parser.add_argument("--reason", default="", help="Close reason.")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY), help="Registry JSON path.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Reconciliation report path.")
    parser.add_argument("--force", action="store_true", help="Force close even if dirty.")
    parser.add_argument("--apply", action="store_true", help="Actually remove the worktree.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    target_path = Path(str(args.path)).expanduser().resolve()
    registry_path = Path(str(args.registry)).expanduser().resolve()
    out_path = Path(str(args.out)).expanduser().resolve()

    report: dict[str, Any] = {
        "kind": "worktree-reconciliation",
        "version": "v1",
        "generated_at": _now_iso(),
        "repo_root": str(ROOT),
        "path": str(target_path),
        "owner": str(args.owner).strip(),
        "reason": str(args.reason).strip(),
        "status": "FAIL",
        "apply": bool(args.apply),
        "force": bool(args.force),
    }

    try:
        if target_path == ROOT.resolve():
            raise RuntimeError("cannot_close_canonical_worktree")

        worktrees = _parse_worktree_list()
        target = next((item for item in worktrees if Path(str(item.get("path") or "")).resolve() == target_path), None)
        if not isinstance(target, dict):
            raise RuntimeError("worktree_not_found")

        dirty_paths = _dirty_paths(target_path)
        report["branch"] = str(target.get("branch") or "")
        report["head"] = str(target.get("head") or "")
        report["dirty_count"] = len(dirty_paths)
        report["dirty_paths"] = dirty_paths
        report["registry_path"] = str(registry_path)

        if dirty_paths and not args.force:
            raise RuntimeError("dirty_worktree_requires_force_or_manual_reconciliation")

        if args.apply:
            cmd = ["worktree", "remove", str(target_path)]
            if args.force:
                cmd.insert(2, "--force")
            _run_git(cmd)
            _update_registry_close(
                registry_path=registry_path,
                target_path=str(target_path),
                owner=str(args.owner).strip(),
                reason=str(args.reason).strip() or "manual_close",
                reconciliation_report=str(out_path),
            )
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

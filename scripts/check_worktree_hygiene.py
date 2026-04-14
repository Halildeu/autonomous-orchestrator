#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


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
# Registry is runtime coordination state — lives outside tracked tree so it is
# shared across worktrees and not subject to branch-switching. Legacy path
# registry/worktrees/worktree_registry.v1.json retained as fallback for migration.
_LEGACY_REGISTRY = CANONICAL_ROOT / "registry" / "worktrees" / "worktree_registry.v1.json"
DEFAULT_REGISTRY = CANONICAL_ROOT / ".worktree-registry.json"
DEFAULT_OUT = ROOT / ".cache" / "reports" / "worktree_hygiene_check.v1.json"


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
            branch_ref = line.split(" ", 1)[1].strip()
            current["branch_ref"] = branch_ref
            current["branch"] = branch_ref.removeprefix("refs/heads/")
        elif line.strip() == "detached":
            current["detached"] = True
        elif line.startswith("locked"):
            current["locked"] = True
        elif line.startswith("prunable"):
            current["prunable"] = True
    if current:
        entries.append(current)
    for item in entries:
        item.setdefault("branch", "")
        item.setdefault("branch_ref", "")
        item.setdefault("detached", False)
        item.setdefault("locked", False)
        item.setdefault("prunable", False)
    return entries


def _parse_status_line(line: str) -> str:
    raw = line[3:] if len(line) >= 4 else line
    if " -> " in raw:
        return raw.split(" -> ", 1)[1].strip()
    return raw.strip()


def _read_dirty_paths(worktree_path: Path) -> list[str]:
    raw = _run_git(["status", "--short"], cwd=worktree_path)
    out: list[str] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        out.append(_parse_status_line(line))
    return out


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _default_registry_entry(*, worktree: dict[str, Any], opened_at: str) -> dict[str, Any]:
    path = str(worktree.get("path") or "")
    is_canonical = Path(path).resolve() == CANONICAL_ROOT.resolve()
    return {
        "path": path,
        "branch": str(worktree.get("branch") or ""),
        "head": str(worktree.get("head") or ""),
        "kind": "canonical" if is_canonical else "side",
        "status": "ACTIVE",
        "owner": "system",
        "purpose": "primary_managed_repo_line" if is_canonical else "bootstrap_detected_side_worktree",
        "intake_id": "",
        "read_only": False if is_canonical else False,
        "allowed_paths": ["**"] if is_canonical else [],
        "opened_at": opened_at,
        "expires_at": "",
        "close_condition": "canonical_never_closed" if is_canonical else "bootstrap_cleanup_or_adopt",
    }


def _bootstrap_registry(*, registry_path: Path, worktrees: list[dict[str, Any]]) -> dict[str, Any]:
    generated_at = _now_iso()
    payload = {
        "version": "v1",
        "generated_at": generated_at,
        "repo_root": str(ROOT),
        "canonical_worktree_path": str(ROOT),
        "entries": [
            _default_registry_entry(worktree=item, opened_at=generated_at)
            for item in worktrees
        ],
        "notes": [
            "BOOTSTRAPPED_FROM_GIT_WORKTREE_LIST=true",
            "MANUAL_ADOPTION_RECOMMENDED_FOR_SIDE_WORKTREES=true",
        ],
    }
    _write_json(registry_path, payload)
    return payload


def _parse_iso(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns if pattern)


def _severity_rank(severity: str) -> int:
    return {"OK": 0, "WARN": 1, "FAIL": 2}.get(severity, 2)


def _build_issue(*, issue_id: str, severity: str, path: str, message: str) -> dict[str, str]:
    return {
        "id": issue_id,
        "severity": severity,
        "path": path,
        "message": message,
    }


def analyze(*, registry_path: Path, bootstrap_registry_if_missing: bool) -> dict[str, Any]:
    worktrees = _parse_worktree_list()
    bootstrapped = False
    if not registry_path.exists() and bootstrap_registry_if_missing:
        _bootstrap_registry(registry_path=registry_path, worktrees=worktrees)
        bootstrapped = True

    registry_obj: dict[str, Any] = {}
    if registry_path.exists():
        registry_obj = _load_json(registry_path)

    registry_entries = registry_obj.get("entries") if isinstance(registry_obj.get("entries"), list) else []
    active_entries = {
        str(item.get("path") or ""): item
        for item in registry_entries
        if isinstance(item, dict) and str(item.get("status") or "ACTIVE").upper() == "ACTIVE"
    }

    now = datetime.now(timezone.utc)
    issues: list[dict[str, str]] = []
    worktree_rows: list[dict[str, Any]] = []
    dirty_side_worktree_count = 0
    dirty_worktree_count = 0
    unregistered_dirty_side_count = 0

    for item in worktrees:
        path = Path(str(item.get("path") or "")).resolve()
        dirty_paths = _read_dirty_paths(path)
        dirty_count = len(dirty_paths)
        is_dirty = dirty_count > 0
        is_canonical = path == CANONICAL_ROOT.resolve()
        entry = active_entries.get(str(path))

        if is_dirty:
            dirty_worktree_count += 1
            if not is_canonical:
                dirty_side_worktree_count += 1
                if entry is None:
                    unregistered_dirty_side_count += 1

        if entry is None:
            severity = "FAIL" if not is_canonical else "WARN"
            issues.append(
                _build_issue(
                    issue_id="UNREGISTERED_WORKTREE",
                    severity=severity,
                    path=str(path),
                    message="Worktree registry kaydi yok.",
                )
            )
        else:
            expires_at = _parse_iso(str(entry.get("expires_at") or ""))
            if expires_at is not None and now >= expires_at:
                issues.append(
                    _build_issue(
                        issue_id="EXPIRED_WORKTREE",
                        severity="FAIL" if is_dirty else "WARN",
                        path=str(path),
                        message="Worktree TTL suresi dolmus.",
                    )
                )
            if not is_canonical and is_dirty:
                allowed_paths = [
                    str(pattern).strip()
                    for pattern in (entry.get("allowed_paths") if isinstance(entry.get("allowed_paths"), list) else [])
                    if str(pattern).strip()
                ]
                if not allowed_paths:
                    issues.append(
                        _build_issue(
                            issue_id="DIRTY_SIDE_WORKTREE_WITHOUT_ALLOWED_PATHS",
                            severity="FAIL",
                            path=str(path),
                            message="Kirli yan masa icin allowed_paths tanimli degil.",
                        )
                    )
                else:
                    outside_paths = [rel for rel in dirty_paths if not _matches_any(rel, allowed_paths)]
                    if outside_paths:
                        issues.append(
                            _build_issue(
                                issue_id="DIRTY_OUTSIDE_ALLOWED_PATHS",
                                severity="FAIL",
                                path=str(path),
                                message="Kirli dosyalar allowed_paths disina tasiyor.",
                            )
                        )
        if is_canonical and is_dirty:
            issues.append(
                _build_issue(
                    issue_id="MAINLINE_DIRTY",
                    severity="FAIL",
                    path=str(path),
                    message="Kanonik ana hat kirli.",
                )
            )

        worktree_rows.append(
            {
                "path": str(path),
                "branch": str(item.get("branch") or ""),
                "head": str(item.get("head") or ""),
                "kind": "canonical" if is_canonical else "side",
                "dirty": is_dirty,
                "dirty_count": dirty_count,
                "dirty_paths": dirty_paths,
                "registered": entry is not None,
                "registry_entry": entry if isinstance(entry, dict) else {},
            }
        )

    actual_paths = {str(Path(str(item.get("path") or "")).resolve()) for item in worktrees}
    for path, entry in active_entries.items():
        if path not in actual_paths:
            issues.append(
                _build_issue(
                    issue_id="REGISTRY_ENTRY_MISSING_FROM_GIT",
                    severity="WARN",
                    path=path,
                    message="Registry kaydi var ama git worktree list icinde gorunmuyor.",
                )
            )

    # Registered dirty side worktrees are expected in multi-agent parallel work.
    # Only UNREGISTERED dirty side worktrees indicate ghost / orphaned sessions.
    if unregistered_dirty_side_count > 0:
        issues.append(
            _build_issue(
                issue_id="UNREGISTERED_DIRTY_SIDE_WORKTREES",
                severity="FAIL",
                path=str(CANONICAL_ROOT),
                message=(
                    f"{unregistered_dirty_side_count} kayit disi kirli yan masa var; "
                    "registry'e adopt et veya temizle."
                ),
            )
        )
    # Soft ceiling: if many registered dirty side worktrees exist, warn (not fail).
    elif dirty_side_worktree_count > 4:
        issues.append(
            _build_issue(
                issue_id="MANY_DIRTY_SIDE_WORKTREES",
                severity="WARN",
                path=str(CANONICAL_ROOT),
                message=(
                    f"{dirty_side_worktree_count} kirli yan masa acik; "
                    "paralel iş yükünü gözden geçir."
                ),
            )
        )

    status = "OK"
    if issues:
        status = "FAIL" if max(_severity_rank(item["severity"]) for item in issues) >= 2 else "WARN"

    recommended_actions: list[str] = []
    if any(item["id"] == "MAINLINE_DIRTY" for item in issues):
        recommended_actions.append("Kanonik hatta yeni yan masa acmadan once temiz status gerektir.")
    if any(item["id"] == "UNREGISTERED_WORKTREE" for item in issues):
        recommended_actions.append("Acilik worktree registry'ye owner/purpose/ttl ile kaydedilmelidir.")
    if any(item["id"] == "UNREGISTERED_DIRTY_SIDE_WORKTREES" for item in issues):
        recommended_actions.append("Kayit disi kirli worktree'leri registry'ye adopt et veya reconcile ederek kapat.")
    if any(item["id"] == "MANY_DIRTY_SIDE_WORKTREES" for item in issues):
        recommended_actions.append("Paralel kirli yan masa sayisi yüksek; tamamlananları merge edip kapat.")
    if any(item["id"] == "DIRTY_OUTSIDE_ALLOWED_PATHS" for item in issues):
        recommended_actions.append("Yan masadaki degisiklikleri allowed_paths ile uyumlu hale getir veya contract kapsamini guncelle.")
    if not recommended_actions:
        recommended_actions.append("Worktree hijyen durumu temiz; kanonik hat uzerinden calismaya devam et.")

    return {
        "kind": "worktree-hygiene-check",
        "version": "v1",
        "generated_at": _now_iso(),
        "repo_root": str(ROOT),
        "canonical_worktree_path": str(ROOT),
        "registry_path": str(registry_path),
        "status": status,
        "registry_bootstrapped": bootstrapped,
        "totals": {
            "worktree_count": len(worktrees),
            "dirty_worktree_count": dirty_worktree_count,
            "dirty_side_worktree_count": dirty_side_worktree_count,
            "active_registry_entries": len(active_entries),
        },
        "worktrees": worktree_rows,
        "issues": issues,
        "recommended_actions": recommended_actions,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check managed repo worktree hygiene against a local registry.")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY), help="Registry JSON path.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Report JSON path.")
    parser.add_argument(
        "--bootstrap-registry-if-missing",
        action="store_true",
        help="Seed registry from current git worktree list if missing.",
    )
    parser.add_argument("--strict", action="store_true", help="Return non-zero on WARN as well.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    registry_path = Path(str(args.registry)).expanduser().resolve()
    out_path = Path(str(args.out)).expanduser().resolve()
    report = analyze(
        registry_path=registry_path,
        bootstrap_registry_if_missing=bool(args.bootstrap_registry_if_missing),
    )
    _write_json(out_path, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    if report["status"] == "FAIL":
        return 2
    if report["status"] == "WARN" and args.strict:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"invalid_json_root:{path}")
    return obj


def _normalize_rel(path: str) -> str:
    norm = str(path or "").strip().replace("\\", "/")
    while norm.startswith("./"):
        norm = norm[2:]
    return norm


def _match_any(path: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if fnmatch.fnmatch(path, pattern):
            return True
    return False


def _git_changed_files(repo_root: Path, base: str, head: str) -> list[str]:
    proc = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "diff",
            "--name-only",
            "--diff-filter=ACMRTUXB",
            base,
            head,
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "git_diff_failed").strip())
    return sorted(
        {
            _normalize_rel(line)
            for line in (proc.stdout or "").splitlines()
            if _normalize_rel(line)
        }
    )


def _default_diff_refs(repo_root: Path) -> tuple[str, str]:
    try:
        left = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD^1"],
            text=True,
            capture_output=True,
            check=False,
        )
        right = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD^2"],
            text=True,
            capture_output=True,
            check=False,
        )
        if left.returncode == 0 and right.returncode == 0:
            base_parent = left.stdout.strip()
            pr_head_parent = right.stdout.strip()
            merge_base = subprocess.run(
                ["git", "-C", str(repo_root), "merge-base", base_parent, pr_head_parent],
                text=True,
                capture_output=True,
                check=False,
            )
            if merge_base.returncode == 0 and merge_base.stdout.strip():
                return merge_base.stdout.strip(), pr_head_parent
    except Exception:
        pass
    return "HEAD~1", "HEAD"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--packet", default="")
    parser.add_argument("--base", default="")
    parser.add_argument("--head", default="")
    parser.add_argument("--changed-files", default="", help="Comma separated file list.")
    parser.add_argument("--out", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = Path(str(args.repo_root)).resolve()
    pm_policy = _load_json(repo_root / "policies/policy_pm_suite.v1.json")
    delivery_session = pm_policy.get("delivery_session") if isinstance(pm_policy.get("delivery_session"), dict) else {}
    packet_rel = str(args.packet).strip() or str(delivery_session.get("packet_path") or "")
    if not packet_rel:
        raise SystemExit("delivery_session_guard failed: packet path missing")
    packet_path = Path(packet_rel)
    if not packet_path.is_absolute():
        packet_path = (repo_root / packet_path).resolve()
    packet = _load_json(packet_path)

    feature_bridge_policy = _load_json(repo_root / "policies/policy_feature_execution_bridge.v1.json")
    scope_detection = (
        feature_bridge_policy.get("scope_detection")
        if isinstance(feature_bridge_policy.get("scope_detection"), dict)
        else {}
    )
    include_globs = [str(x).strip() for x in (scope_detection.get("include_globs") or []) if str(x).strip()]
    exclude_globs = [str(x).strip() for x in (scope_detection.get("exclude_globs") or []) if str(x).strip()]
    scope_globs = scope_detection.get("scope_globs") if isinstance(scope_detection.get("scope_globs"), dict) else {}

    changed_files: list[str] = []
    diff_base = str(args.base or "").strip()
    diff_head = str(args.head or "").strip()
    try:
        raw_changed = str(args.changed_files or "").strip()
        if raw_changed:
            changed_files = sorted(
                {
                    _normalize_rel(item)
                    for item in raw_changed.split(",")
                    if _normalize_rel(item)
                }
            )
        else:
            if not diff_base or not diff_head:
                diff_base, diff_head = _default_diff_refs(repo_root)
            changed_files = _git_changed_files(repo_root, diff_base, diff_head)
    except Exception as exc:
        report = {
            "version": "v1",
            "kind": "delivery-session-guard-report",
            "generated_at": _now_iso(),
            "status": "FAIL",
            "errors": [f"diff_collect_failed:{exc}"],
            "warnings": [],
        }
        out_path = Path(str(args.out).strip() or str(delivery_session.get("guard_report_path") or ""))
        if not out_path.is_absolute():
            out_path = (repo_root / out_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": "FAIL", "errors": 1, "out": str(out_path)}, ensure_ascii=False))
        return 2

    allowed_write_paths = [
        str(item).strip()
        for item in (packet.get("allowed_write_paths") or [])
        if isinstance(item, str) and str(item).strip()
    ]
    active_scopes = {
        str(item).strip()
        for item in (packet.get("active_scopes") or [])
        if isinstance(item, str) and str(item).strip()
    }
    packet_ux = packet.get("ux_context") if isinstance(packet.get("ux_context"), dict) else {}
    ux_artifacts = packet_ux.get("artifacts") if isinstance(packet_ux.get("artifacts"), list) else []
    ux_globs = [str(item.get("path_glob") or "").strip() for item in ux_artifacts if isinstance(item, dict)]

    relevant_changed_files = [
        path
        for path in changed_files
        if (not include_globs or _match_any(path, include_globs))
        and not _match_any(path, exclude_globs)
    ]
    errors: list[str] = []
    warnings: list[str] = []

    for path in relevant_changed_files:
        if not _match_any(path, allowed_write_paths):
            errors.append(f"write_outside_packet:{path}")

    detected_scopes: set[str] = set()
    for scope_name, patterns in scope_globs.items():
        if not isinstance(patterns, list):
            continue
        normalized_patterns = [str(item).strip() for item in patterns if isinstance(item, str) and str(item).strip()]
        if any(_match_any(path, normalized_patterns) for path in relevant_changed_files):
            detected_scopes.add(str(scope_name))
    extra_scopes = sorted(detected_scopes - active_scopes)
    if extra_scopes:
        errors.append(f"scope_expansion_detected:{','.join(extra_scopes)}")

    frontend_changed = "frontend" in detected_scopes
    if frontend_changed and str(packet_ux.get("mode") or "") != "REQUIRED":
        errors.append("frontend_change_without_required_ux_context")
    if frontend_changed:
        uncovered_ui = [
            path
            for path in relevant_changed_files
            if any(
                _match_any(path, [str(item).strip() for item in patterns if isinstance(item, str)])
                for scope_name, patterns in scope_globs.items()
                if scope_name == "frontend" and isinstance(patterns, list)
            )
            and not _match_any(path, ux_globs)
        ]
        if uncovered_ui:
            errors.extend([f"frontend_change_outside_ux_artifacts:{path}" for path in uncovered_ui])

    out_text = str(args.out).strip() or str(delivery_session.get("guard_report_path") or "")
    if not out_text:
        raise SystemExit("delivery_session_guard failed: out path missing")
    out_path = Path(out_text)
    if not out_path.is_absolute():
        out_path = (repo_root / out_path).resolve()

    status = "FAIL" if errors else "OK"
    report = {
        "version": "v1",
        "kind": "delivery-session-guard-report",
        "generated_at": _now_iso(),
        "status": status,
        "repo_root": str(repo_root),
        "packet_path": str(packet_path),
        "diff": {
            "base": diff_base,
            "head": diff_head,
            "changed_files_count": len(changed_files),
            "relevant_changed_files_count": len(relevant_changed_files),
            "relevant_changed_files": relevant_changed_files,
        },
        "active_scopes": sorted(active_scopes),
        "detected_scopes": sorted(detected_scopes),
        "errors": errors,
        "warnings": warnings,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": status,
                "errors": len(errors),
                "warnings": len(warnings),
                "detected_scopes": sorted(detected_scopes),
                "out": str(out_path),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if status == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())

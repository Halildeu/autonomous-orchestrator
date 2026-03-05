#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"json_root_not_object:{path}")
    return obj


def _safe_status(value: Any, *, default: str = "UNKNOWN") -> str:
    status = str(value or "").strip().upper()
    if status in {"OK", "WARN", "FAIL", "UNVERIFIED", "UNKNOWN", "IDLE"}:
        return status
    return default


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--manifest-path", default=".cache/managed_repos.v1.json")
    parser.add_argument("--sync-report-path", default=".cache/reports/managed_repo_standards_sync/report.v1.json")
    parser.add_argument("--out", default=".cache/reports/release-evidence/managed_repo_standards_dashboard.v1.json")
    return parser.parse_args(argv)


def _resolve_path(base: Path, raw: str) -> Path:
    p = Path(str(raw).strip() or ".")
    return p.resolve() if p.is_absolute() else (base / p).resolve()


def _tail(text: str, *, limit: int = 8) -> list[str]:
    lines = [line for line in str(text or "").splitlines() if line.strip()]
    return lines[-limit:]


def _extract_json_from_stdout(stdout: str) -> dict[str, Any] | None:
    for line in reversed(str(stdout or "").splitlines()):
        raw = line.strip()
        if not raw.startswith("{") or not raw.endswith("}"):
            continue
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _run_json_cmd(cmd: list[str], *, cwd: Path) -> dict[str, Any]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=300)
    except FileNotFoundError:
        return {
            "returncode": 127,
            "status": "UNKNOWN",
            "error": "binary_missing",
            "payload": {},
            "stdout_tail": [],
            "stderr_tail": [],
        }
    except subprocess.TimeoutExpired:
        return {
            "returncode": 124,
            "status": "UNKNOWN",
            "error": "timeout",
            "payload": {},
            "stdout_tail": [],
            "stderr_tail": [],
        }
    payload = _extract_json_from_stdout(proc.stdout) or {}
    return {
        "returncode": int(proc.returncode),
        "status": _safe_status(payload.get("status"), default=("OK" if proc.returncode == 0 else "FAIL")),
        "payload": payload,
        "stdout_tail": _tail(proc.stdout),
        "stderr_tail": _tail(proc.stderr),
    }


def _sync_result_by_repo(sync_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = sync_report.get("results")
    if not isinstance(rows, list):
        return {}
    mapping: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        repo_root = str(row.get("repo_root") or "").strip()
        if not repo_root:
            continue
        mapping[repo_root] = row
    return mapping


def _read_repo_lock(repo_root: Path) -> tuple[str, dict[str, Any], list[str]]:
    lock_path = repo_root / "standards.lock"
    if not lock_path.exists():
        return "FAIL", {}, ["standards.lock_missing"]
    try:
        lock = _load_json(lock_path)
    except Exception:
        return "FAIL", {}, ["standards.lock_invalid_json"]
    return "OK", lock, []


def _check_required_files(repo_root: Path, required_files: list[str]) -> list[str]:
    missing: list[str] = []
    for rel in required_files:
        path = repo_root / rel
        if not path.exists():
            missing.append(rel)
    return missing


def _repo_row(
    *,
    repo_root: Path,
    expected_source_keys: set[str],
    expected_required_files: list[str],
    sync_row: dict[str, Any] | None,
) -> dict[str, Any]:
    unknown_signals: list[str] = []

    lock_status, repo_lock, lock_signals = _read_repo_lock(repo_root)
    unknown_signals.extend(lock_signals)
    repo_source_map = repo_lock.get("standard_sources") if isinstance(repo_lock.get("standard_sources"), dict) else {}
    source_keys = {str(k).strip() for k in repo_source_map.keys() if str(k).strip()}
    source_missing_keys = sorted(expected_source_keys - source_keys)
    source_extra_keys = sorted(source_keys - expected_source_keys)

    source_missing_paths: list[str] = []
    for key in sorted(expected_source_keys):
        rel = str(repo_source_map.get(key) or "").strip()
        if not rel:
            source_missing_paths.append(f"{key}:path_missing")
            continue
        if not (repo_root / rel).exists():
            source_missing_paths.append(f"{key}:{rel}")

    missing_required_files = _check_required_files(repo_root, expected_required_files)

    standards_lock_cmd = [str((repo_root / "ci" / "check_standards_lock.py").resolve())]
    standards_lock_status = "UNKNOWN"
    standards_lock_payload: dict[str, Any] = {}
    standards_lock_cmd_path = repo_root / "ci" / "check_standards_lock.py"
    standards_lock_rc = 127
    standards_lock_stderr_tail: list[str] = []
    if standards_lock_cmd_path.exists():
        res = _run_json_cmd(
            ["python3", str(standards_lock_cmd_path), "--repo-root", str(repo_root)],
            cwd=repo_root,
        )
        standards_lock_status = _safe_status(res.get("status"))
        standards_lock_payload = res.get("payload") if isinstance(res.get("payload"), dict) else {}
        standards_lock_rc = int(res.get("returncode") or 0)
        standards_lock_stderr_tail = [str(x) for x in (res.get("stderr_tail") if isinstance(res.get("stderr_tail"), list) else [])]
        if standards_lock_payload == {}:
            unknown_signals.append("check_standards_lock_payload_missing")
    else:
        unknown_signals.append("check_standards_lock_script_missing")

    checklist_status = "UNKNOWN"
    checklist_summary: dict[str, Any] = {}
    checklist_non_ok: list[dict[str, Any]] = []
    checklist_cmd_path = repo_root / "scripts" / "ops_technical_baseline_checklist.py"
    if checklist_cmd_path.exists():
        out_path = repo_root / ".cache" / "reports" / "technical_baseline_checklist.v1.json"
        res = _run_json_cmd(
            ["python3", str(checklist_cmd_path), "--repo-root", str(repo_root), "--out", str(out_path)],
            cwd=repo_root,
        )
        checklist_status = _safe_status(res.get("status"))
        if out_path.exists():
            try:
                report = _load_json(out_path)
            except Exception:
                report = {}
                unknown_signals.append("technical_baseline_checklist_report_invalid_json")
            if isinstance(report.get("summary"), dict):
                checklist_summary = report.get("summary")  # type: ignore[assignment]
            sections = report.get("sections")
            if isinstance(sections, dict):
                for section_name, section_obj in sections.items():
                    if not isinstance(section_obj, dict):
                        continue
                    checks = section_obj.get("checks")
                    if not isinstance(checks, list):
                        continue
                    for item in checks:
                        if not isinstance(item, dict):
                            continue
                        status = _safe_status(item.get("status"))
                        if status == "OK":
                            continue
                        checklist_non_ok.append(
                            {
                                "section": str(section_name),
                                "id": str(item.get("id") or ""),
                                "status": status,
                                "actual": str(item.get("actual") or ""),
                                "expected": str(item.get("expected") or ""),
                            }
                        )
        else:
            unknown_signals.append("technical_baseline_checklist_report_missing")
    else:
        unknown_signals.append("ops_technical_baseline_checklist_script_missing")

    lane_status = "UNKNOWN"
    lane_cmd_path = repo_root / "ci" / "check_module_delivery_lanes.py"
    lane_rc = 127
    if lane_cmd_path.exists():
        lane_res = _run_json_cmd(
            ["python3", str(lane_cmd_path), "--strict"],
            cwd=repo_root,
        )
        lane_status = _safe_status(lane_res.get("status"))
        lane_rc = int(lane_res.get("returncode") or 0)
    else:
        unknown_signals.append("check_module_delivery_lanes_script_missing")

    sync_status = "UNKNOWN"
    branch_status = "UNVERIFIED"
    branch_missing_required_checks: list[str] = []
    branch_repo_slug = ""
    if isinstance(sync_row, dict):
        sync_status = _safe_status(sync_row.get("status"))
        branch = sync_row.get("branch_protection") if isinstance(sync_row.get("branch_protection"), dict) else {}
        branch_status = _safe_status(branch.get("status"), default="UNVERIFIED")
        branch_repo_slug = str(branch.get("repo_slug") or "")
        branch_missing_required_checks = [
            str(item)
            for item in (
                branch.get("missing_required_checks")
                if isinstance(branch.get("missing_required_checks"), list)
                else []
            )
        ]
        if not branch_repo_slug:
            unknown_signals.append("branch_protection_repo_slug_missing")
        if branch_status in {"UNKNOWN", "UNVERIFIED"}:
            unknown_signals.append("branch_protection_unverified")
    else:
        unknown_signals.append("sync_result_missing_for_repo")

    if source_missing_keys:
        unknown_signals.append("standard_sources_keys_drift")
    if source_extra_keys:
        unknown_signals.append("standard_sources_extra_keys_present")
    if source_missing_paths:
        unknown_signals.append("standard_source_paths_missing")
    if missing_required_files:
        unknown_signals.append("required_files_missing")

    status = "OK"
    if (
        lock_status != "OK"
        or standards_lock_status != "OK"
        or missing_required_files
        or source_missing_keys
        or source_missing_paths
        or lane_status != "OK"
    ):
        status = "FAIL"
    elif checklist_non_ok or source_extra_keys or branch_status in {"UNVERIFIED", "UNKNOWN", "WARN"}:
        status = "WARN"

    return {
        "repo_root": str(repo_root),
        "status": status,
        "standards_lock": {
            "status": lock_status,
            "check_status": standards_lock_status,
            "check_returncode": standards_lock_rc,
            "check_payload": standards_lock_payload,
            "check_stderr_tail": standards_lock_stderr_tail,
        },
        "standard_sources": {
            "expected_keys_count": len(expected_source_keys),
            "actual_keys_count": len(source_keys),
            "missing_keys": source_missing_keys,
            "extra_keys": source_extra_keys,
            "missing_paths": source_missing_paths,
        },
        "required_files": {
            "expected_count": len(expected_required_files),
            "missing_count": len(missing_required_files),
            "missing": missing_required_files,
        },
        "technical_baseline_checklist": {
            "status": checklist_status,
            "summary": checklist_summary,
            "non_ok": checklist_non_ok,
            "non_ok_count": len(checklist_non_ok),
        },
        "module_delivery_lanes": {
            "status": lane_status,
            "returncode": lane_rc,
        },
        "sync": {
            "status": sync_status,
            "branch_protection_status": branch_status,
            "branch_repo_slug": branch_repo_slug,
            "branch_missing_required_checks": branch_missing_required_checks,
        },
        "unknown_signals": sorted(set(unknown_signals)),
    }


def _overall_status(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "WARN"
    if any(str(row.get("status")) == "FAIL" for row in rows):
        return "FAIL"
    if any(str(row.get("status")) == "WARN" for row in rows):
        return "WARN"
    return "OK"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    cwd = Path.cwd().resolve()
    workspace_root = _resolve_path(cwd, str(args.workspace_root))
    manifest_path = _resolve_path(workspace_root, str(args.manifest_path))
    sync_report_path = _resolve_path(workspace_root, str(args.sync_report_path))
    out_path = _resolve_path(workspace_root, str(args.out))
    out_path.parent.mkdir(parents=True, exist_ok=True)

    unknown_signals: list[str] = []

    standards_lock_path = workspace_root / "standards.lock"
    if not standards_lock_path.exists():
        payload = {
            "status": "FAIL",
            "error_code": "STANDARDS_LOCK_MISSING",
            "standards_lock_path": str(standards_lock_path),
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2
    standards_lock = _load_json(standards_lock_path)
    expected_source_keys = {
        str(key).strip()
        for key in (
            standards_lock.get("standard_sources").keys()
            if isinstance(standards_lock.get("standard_sources"), dict)
            else []
        )
        if str(key).strip()
    }
    expected_required_files = [
        str(item).strip()
        for item in (standards_lock.get("required_files") if isinstance(standards_lock.get("required_files"), list) else [])
        if isinstance(item, str) and str(item).strip()
    ]

    manifest: dict[str, Any] = {}
    repos: list[Path] = []
    if manifest_path.exists():
        try:
            manifest = _load_json(manifest_path)
        except Exception:
            unknown_signals.append("managed_repos_manifest_invalid_json")
        raw_repos = manifest.get("repos") if isinstance(manifest.get("repos"), list) else []
        for item in raw_repos:
            if not isinstance(item, dict):
                continue
            repo_root_text = str(item.get("repo_root") or "").strip()
            if not repo_root_text:
                continue
            repos.append(_resolve_path(workspace_root, repo_root_text))
    else:
        unknown_signals.append("managed_repos_manifest_missing")

    if not repos:
        unknown_signals.append("managed_repos_empty")

    sync_report: dict[str, Any] = {}
    if sync_report_path.exists():
        try:
            sync_report = _load_json(sync_report_path)
        except Exception:
            unknown_signals.append("managed_repo_sync_report_invalid_json")
    else:
        unknown_signals.append("managed_repo_sync_report_missing")
    sync_by_repo = _sync_result_by_repo(sync_report)

    rows: list[dict[str, Any]] = []
    for repo_root in repos:
        row = _repo_row(
            repo_root=repo_root,
            expected_source_keys=expected_source_keys,
            expected_required_files=expected_required_files,
            sync_row=sync_by_repo.get(str(repo_root)),
        )
        rows.append(row)

    status = _overall_status(rows)
    if unknown_signals and status == "OK":
        status = "WARN"

    dashboard = {
        "version": "v1",
        "kind": "managed-repo-standards-dashboard",
        "generated_at": _now_iso_utc(),
        "status": status,
        "workspace_root": str(workspace_root),
        "inputs": {
            "standards_lock_path": str(standards_lock_path),
            "manifest_path": str(manifest_path),
            "sync_report_path": str(sync_report_path),
        },
        "summary": {
            "managed_repo_count": len(rows),
            "ok_count": sum(1 for row in rows if str(row.get("status")) == "OK"),
            "warn_count": sum(1 for row in rows if str(row.get("status")) == "WARN"),
            "fail_count": sum(1 for row in rows if str(row.get("status")) == "FAIL"),
            "unknown_signal_count": len(unknown_signals) + sum(len(row.get("unknown_signals", [])) for row in rows),
            "missing_required_files_total": sum(
                int(((row.get("required_files") if isinstance(row.get("required_files"), dict) else {}).get("missing_count") or 0))
                for row in rows
            ),
            "checklist_non_ok_total": sum(
                int(
                    (
                        (row.get("technical_baseline_checklist") if isinstance(row.get("technical_baseline_checklist"), dict) else {})
                        .get("non_ok_count")
                        or 0
                    )
                )
                for row in rows
            ),
        },
        "unknown_signals": sorted(set(unknown_signals)),
        "repos": rows,
    }

    out_path.write_text(json.dumps(dashboard, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    payload = {
        "status": status,
        "managed_repo_count": len(rows),
        "unknown_signal_count": dashboard["summary"]["unknown_signal_count"],
        "out": str(out_path),
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if status in {"OK", "WARN"} else 2


if __name__ == "__main__":
    raise SystemExit(main())

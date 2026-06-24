from __future__ import annotations

from pathlib import Path
from typing import Any

from src.ops.system_status_sections import _load_json, _rel_to_workspace

def _module_delivery_section_impl(workspace_root: Path) -> dict[str, Any] | None:
    report_dir = workspace_root / ".cache" / "reports" / "module_delivery_lanes"
    if not report_dir.exists() or not report_dir.is_dir():
        return None

    report_paths = sorted(report_dir.glob("*.v1.json"))
    if not report_paths:
        return None

    lanes_total = len(report_paths)
    lanes_ok = 0
    lanes_fail = 0
    lanes_warn = 0
    timed_out_count = 0
    invalid_report_count = 0
    latest_finished_at = ""
    latest_failed_key: tuple[str, str] | None = None
    latest_failed: dict[str, Any] | None = None
    notes: list[str] = []

    for path in report_paths:
        rel_path = _rel_to_workspace(path, workspace_root)
        try:
            obj = _load_json(path)
        except Exception:
            invalid_report_count += 1
            notes.append(f"invalid_report:{Path(rel_path).name}")
            continue
        if not isinstance(obj, dict):
            invalid_report_count += 1
            notes.append(f"invalid_report:{Path(rel_path).name}")
            continue

        status = str(obj.get("status") or "WARN")
        if status == "OK":
            lanes_ok += 1
        elif status == "FAIL":
            lanes_fail += 1
        else:
            lanes_warn += 1

        if bool(obj.get("timed_out", False)):
            timed_out_count += 1

        finished_at = str(obj.get("finished_at") or "")
        if finished_at and finished_at > latest_finished_at:
            latest_finished_at = finished_at

        if status != "FAIL":
            continue

        current_key = (finished_at or "", rel_path)
        if latest_failed_key is None or current_key > latest_failed_key:
            latest_failed_key = current_key
            latest_failed = {
                "lane": str(obj.get("lane") or path.stem.replace(".v1", "")),
                "report_path": rel_path,
                "return_code": int(obj.get("return_code") or 0),
                "stdout_preview": "\n".join(
                    [str(line) for line in obj.get("stdout_tail", []) if isinstance(line, str)]
                ).strip(),
                "stderr_preview": "\n".join(
                    [str(line) for line in obj.get("stderr_tail", []) if isinstance(line, str)]
                ).strip(),
            }

    status = "OK"
    if lanes_fail > 0:
        status = "FAIL"
    elif lanes_warn > 0 or invalid_report_count > 0:
        status = "WARN"

    if timed_out_count > 0:
        notes.append(f"timed_out_count={timed_out_count}")

    failed_lane = ""
    failed_report_path = ""
    failed_return_code = 0
    failed_stdout_preview = ""
    failed_stderr_preview = ""
    if isinstance(latest_failed, dict):
        failed_lane = str(latest_failed.get("lane") or "")
        failed_report_path = str(latest_failed.get("report_path") or "")
        failed_return_code = int(latest_failed.get("return_code") or 0)
        failed_stdout_preview = str(latest_failed.get("stdout_preview") or "")
        failed_stderr_preview = str(latest_failed.get("stderr_preview") or "")

    return {
        "status": status,
        "report_dir": str(Path(".cache") / "reports" / "module_delivery_lanes"),
        "lanes_total": int(lanes_total),
        "lanes_ok": int(lanes_ok),
        "lanes_fail": int(lanes_fail),
        "lanes_warn": int(lanes_warn),
        "timed_out_count": int(timed_out_count),
        "invalid_report_count": int(invalid_report_count),
        "latest_finished_at": latest_finished_at,
        "last_failed_lane": failed_lane,
        "last_failed_report_path": failed_report_path,
        "last_failed_return_code": int(failed_return_code),
        "last_failed_stdout_preview": failed_stdout_preview,
        "last_failed_stderr_preview": failed_stderr_preview,
        "notes": sorted(set(notes)),
    }

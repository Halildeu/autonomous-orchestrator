from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def _truncate(s: str, limit: int = 300) -> str:
    if len(s) <= limit:
        return s
    return s[: max(0, limit - 3)] + "..."


def _as_relpath(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def run_policy_review(envelope: dict[str, Any], workspace: str) -> dict[str, Any]:
    ws = Path(workspace).resolve()
    outdir_rel = Path(".cache") / "policy_review"
    outdir = ws / outdir_rel
    outdir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "src.ops.manage",
        "policy-check",
        "--source",
        "both",
        "--outdir",
        str(outdir_rel),
    ]

    env = dict(os.environ)
    # Keep policy review runs read/write safe in dry_run by preventing supply-chain
    # outputs outside .cache (sbom/sign/verify default to supply_chain/).
    env["POLICY_CHECK_SKIP_SUPPLY_CHAIN"] = "1"

    proc = subprocess.run(
        cmd,
        cwd=str(ws),
        text=True,
        capture_output=True,
        env=env,
    )

    sim_path = outdir / "sim_report.json"
    diff_path = outdir / "policy_diff_report.json"
    report_path = outdir / "POLICY_REPORT.md"

    tool_calls = [
        {
            "tool": "policy_check",
            "status": "OK" if proc.returncode == 0 else "FAIL",
            "args_summary": {"source": "both", "outdir": str(outdir_rel)},
            "returncode": proc.returncode,
        }
    ]

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or "policy-check failed"
        return {
            "status": "FAIL",
            "outdir": str(outdir_rel),
            "report_relpath": "POLICY_REPORT.md",
            "sim_counts": {},
            "diff_nonzero": 0,
            "report_bytes": 0,
            "error": _truncate(err, 300),
            "tool_calls": tool_calls,
        }

    sim_counts: dict[str, int] = {}
    try:
        sim_obj = json.loads(sim_path.read_text(encoding="utf-8"))
        counts = sim_obj.get("counts") if isinstance(sim_obj, dict) else None
        if isinstance(counts, dict):
            for k, v in counts.items():
                if isinstance(k, str) and isinstance(v, int):
                    sim_counts[k] = int(v)
    except Exception:
        sim_counts = {}

    diff_nonzero = 0
    try:
        diff_obj = json.loads(diff_path.read_text(encoding="utf-8"))
        if isinstance(diff_obj, dict) and diff_obj.get("status") == "SKIPPED":
            diff_nonzero = 0
        else:
            diff_counts = diff_obj.get("diff_counts") if isinstance(diff_obj, dict) else None
            if isinstance(diff_counts, dict):
                diff_nonzero = sum(int(v) for v in diff_counts.values() if isinstance(v, int) and v > 0)
    except Exception:
        diff_nonzero = 0

    report_bytes = 0
    try:
        report_bytes = report_path.stat().st_size
    except Exception:
        report_bytes = 0

    return {
        "status": "OK",
        "outdir": str(outdir_rel),
        "report_relpath": "POLICY_REPORT.md",
        "sim_counts": sim_counts,
        "diff_nonzero": diff_nonzero,
        "report_bytes": int(report_bytes),
        "report_path": _as_relpath(report_path, ws),
        "tool_calls": tool_calls,
    }


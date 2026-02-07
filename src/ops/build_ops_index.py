from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_root() -> Path:
    # src/ops/build_ops_index.py -> repo root
    return Path(__file__).resolve().parents[2]


def _ensure_inside_workspace(workspace_root: Path, target: Path) -> None:
    workspace_root = workspace_root.resolve()
    target = target.resolve()
    try:
        target.relative_to(workspace_root)
    except Exception as e:
        raise ValueError(f"Path escapes workspace_root: {target}") from e


@dataclass(frozen=True)
class OpsIndexPolicy:
    enabled: bool
    out_run_index: str
    out_dlq_index: str
    max_run_dirs: int
    max_dlq_items: int
    include_prefixes: list[str]
    mode: str
    on_fail: str


def _load_policy(core_root: Path) -> OpsIndexPolicy:
    path = core_root / "policies" / "policy_ops_index.v1.json"
    defaults = OpsIndexPolicy(
        enabled=True,
        out_run_index=".cache/index/run_index.v1.json",
        out_dlq_index=".cache/index/dlq_index.v1.json",
        max_run_dirs=200,
        max_dlq_items=500,
        include_prefixes=["roadmap_finish", "roadmap_orchestrator", "roadmap"],
        mode="bounded",
        on_fail="warn",
    )
    if not path.exists():
        return defaults

    try:
        obj = _load_json(path)
    except Exception:
        return defaults
    if not isinstance(obj, dict):
        return defaults

    enabled = bool(obj.get("enabled", defaults.enabled))
    out_run_index = obj.get("out_run_index", defaults.out_run_index)
    out_dlq_index = obj.get("out_dlq_index", defaults.out_dlq_index)
    include_raw = obj.get("include_prefixes", defaults.include_prefixes)

    include_prefixes = (
        [str(x) for x in include_raw if isinstance(x, str) and x.strip()] if isinstance(include_raw, list) else []
    )
    if not include_prefixes:
        include_prefixes = defaults.include_prefixes

    def _int_or_default(val: Any, dflt: int) -> int:
        try:
            return max(0, int(val))
        except Exception:
            return dflt

    max_run_dirs = _int_or_default(obj.get("max_run_dirs", defaults.max_run_dirs), defaults.max_run_dirs)
    max_dlq_items = _int_or_default(obj.get("max_dlq_items", defaults.max_dlq_items), defaults.max_dlq_items)

    mode = obj.get("mode", defaults.mode)
    if mode not in {"bounded"}:
        mode = defaults.mode

    on_fail = obj.get("on_fail", defaults.on_fail)
    if on_fail not in {"warn", "block"}:
        on_fail = defaults.on_fail

    if not isinstance(out_run_index, str) or not out_run_index.strip():
        out_run_index = defaults.out_run_index
    if not isinstance(out_dlq_index, str) or not out_dlq_index.strip():
        out_dlq_index = defaults.out_dlq_index

    return OpsIndexPolicy(
        enabled=enabled,
        out_run_index=str(out_run_index),
        out_dlq_index=str(out_dlq_index),
        max_run_dirs=max_run_dirs,
        max_dlq_items=max_dlq_items,
        include_prefixes=include_prefixes,
        mode=mode,
        on_fail=on_fail,
    )


def _parse_dlq_created_at(name: str) -> str | None:
    m = re.match(r"^(?P<date>\d{8})(?:[-_](?P<time>\d{6}))?", name)
    if not m:
        return None
    date_s = m.group("date")
    time_s = m.group("time") or "000000"
    try:
        dt = datetime.strptime(date_s + time_s, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except Exception:
        return None
    return dt.isoformat().replace("+00:00", "Z")


def _collect_dlq_index(
    *,
    dlq_dir: Path,
    max_items: int,
) -> tuple[list[dict[str, Any]], int]:
    parse_errors = 0
    items: list[dict[str, Any]] = []
    if not dlq_dir.exists() or not dlq_dir.is_dir():
        return (items, parse_errors)

    paths = sorted([p for p in dlq_dir.glob("*.json") if p.is_file()], key=lambda p: p.name, reverse=True)
    if max_items > 0:
        paths = paths[: int(max_items)]

    for p in paths:
        try:
            obj = _load_json(p)
        except Exception:
            parse_errors += 1
            continue
        if not isinstance(obj, dict):
            parse_errors += 1
            continue
        stage = obj.get("stage") if isinstance(obj.get("stage"), str) else None
        error_code = obj.get("error_code") if isinstance(obj.get("error_code"), str) else None
        items.append(
            {
                "filename": p.name,
                "created_at": _parse_dlq_created_at(p.name),
                "stage": stage,
                "error_code": error_code,
            }
        )

    return (items, parse_errors)


def _collect_run_index(
    *,
    core_root: Path,
    include_prefixes: list[str],
    max_run_dirs: int,
) -> tuple[list[dict[str, Any]], int]:
    parse_errors = 0
    run_items: list[dict[str, Any]] = []
    evidence_root = core_root / "evidence"
    if not evidence_root.exists():
        return (run_items, parse_errors)

    candidates: list[Path] = []
    for prefix in include_prefixes:
        base = (evidence_root / prefix).resolve()
        if not base.exists() or not base.is_dir():
            continue
        for child in base.iterdir():
            if child.is_dir():
                candidates.append(child)

    candidates = sorted(candidates, key=lambda p: p.as_posix())
    if max_run_dirs > 0:
        candidates = candidates[-int(max_run_dirs) :]

    for run_dir in candidates:
        summary_path = run_dir / "summary.json"
        if not summary_path.exists():
            continue
        try:
            summary = _load_json(summary_path)
        except Exception:
            parse_errors += 1
            continue
        if not isinstance(summary, dict):
            parse_errors += 1
            continue
        result_state = summary.get("result_state") or summary.get("status")
        result_state = result_state if isinstance(result_state, str) else None
        finished_at = summary.get("finished_at") if isinstance(summary.get("finished_at"), str) else None
        run_items.append(
            {
                "run_id": run_dir.name,
                "result_state": result_state,
                "finished_at": finished_at,
                "evidence_path": run_dir.relative_to(core_root).as_posix(),
            }
        )

    return (run_items, parse_errors)


def build_ops_index(*, workspace_root: Path, core_root: Path | None = None, outdir: Path | None = None) -> dict[str, Any]:
    core_root = core_root or _repo_root()
    policy = _load_policy(core_root)

    if not policy.enabled:
        return {"status": "SKIPPED", "reason": "POLICY_DISABLED"}

    workspace_root = workspace_root.resolve()

    if outdir is None:
        run_index_path = (workspace_root / policy.out_run_index).resolve()
        dlq_index_path = (workspace_root / policy.out_dlq_index).resolve()
    else:
        outdir = outdir.resolve()
        run_index_path = (outdir / Path(policy.out_run_index).name).resolve()
        dlq_index_path = (outdir / Path(policy.out_dlq_index).name).resolve()

    _ensure_inside_workspace(workspace_root, run_index_path)
    _ensure_inside_workspace(workspace_root, dlq_index_path)

    dlq_dir_ws = workspace_root / "dlq"
    dlq_dir_core = core_root / "dlq"
    dlq_dir = dlq_dir_ws if dlq_dir_ws.exists() else dlq_dir_core
    dlq_source = "workspace" if dlq_dir == dlq_dir_ws else "core"

    dlq_items, dlq_parse_errors = _collect_dlq_index(
        dlq_dir=dlq_dir,
        max_items=int(policy.max_dlq_items),
    )

    run_items, run_parse_errors = _collect_run_index(
        core_root=core_root,
        include_prefixes=policy.include_prefixes,
        max_run_dirs=int(policy.max_run_dirs),
    )

    run_index = {
        "version": "v1",
        "generated_at": _now_iso8601(),
        "source": "core",
        "items": run_items,
        "parse_errors": int(run_parse_errors),
    }
    dlq_index = {
        "version": "v1",
        "generated_at": _now_iso8601(),
        "source": dlq_source,
        "items": dlq_items,
        "parse_errors": int(dlq_parse_errors),
    }

    status = "OK"
    if run_parse_errors or dlq_parse_errors:
        status = "WARN"

    try:
        run_index_path.parent.mkdir(parents=True, exist_ok=True)
        run_index_path.write_text(_dump_json(run_index), encoding="utf-8")
        dlq_index_path.parent.mkdir(parents=True, exist_ok=True)
        dlq_index_path.write_text(_dump_json(dlq_index), encoding="utf-8")
    except Exception as e:
        return {
            "status": "FAIL",
            "error_code": "OPS_INDEX_FAIL",
            "message": str(e)[:300],
            "run_count": len(run_items),
            "dlq_count": len(dlq_items),
        }

    return {
        "status": status,
        "run_count": len(run_items),
        "dlq_count": len(dlq_items),
        "parse_errors": int(run_parse_errors + dlq_parse_errors),
        "out_paths": [run_index_path.as_posix(), dlq_index_path.as_posix()],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.ops.build_ops_index")
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--outdir", default=None, help="Optional output dir (defaults to policy paths).")
    args = ap.parse_args(argv)

    workspace_root = Path(str(args.workspace_root)).resolve()
    if not workspace_root.exists() or not workspace_root.is_dir():
        print(json.dumps({"status": "FAIL", "error_code": "WORKSPACE_ROOT_INVALID"}, ensure_ascii=False, sort_keys=True))
        return 2

    outdir = Path(str(args.outdir)).resolve() if args.outdir else None
    report = build_ops_index(workspace_root=workspace_root, outdir=outdir)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))

    status = report.get("status")
    if status in {"OK", "WARN", "SKIPPED"}:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

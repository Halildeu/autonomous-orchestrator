from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FileLineLimit:
    path: str
    soft: int
    hard: int


@dataclass(frozen=True)
class FunctionLineLimits:
    soft: int
    hard: int


@dataclass(frozen=True)
class PythonFileLimits:
    soft_lines: int
    hard_lines: int


@dataclass(frozen=True)
class GrandfatheredFile:
    path: str
    mode: str
    current_lines: int
    max_allowed_lines: int
    expires_on: str | None
    target_soft: int | None
    target_hard: int | None


@dataclass(frozen=True)
class ScriptBudgetConfig:
    python_file_limits: PythonFileLimits
    grandfathered_files: dict[str, GrandfatheredFile]
    file_line_limits: list[FileLineLimit]
    function_line_limits: FunctionLineLimits
    function_scan_paths: list[str]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _require_relative_to_root(repo_root: Path, rel_path: str) -> Path:
    p = (repo_root / rel_path).resolve()
    try:
        p.relative_to(repo_root.resolve())
    except Exception as e:
        raise ValueError(f"PATH_OUTSIDE_REPO: {rel_path}") from e
    return p


def _count_lines(path: Path) -> int:
    return len(path.read_bytes().splitlines())


def _count_lines_from_bytes(data: bytes) -> int:
    return len(data.splitlines())


def _is_git_work_tree(repo_root: Path) -> bool:
    try:
        p = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        return p.returncode == 0 and (p.stdout or "").strip().lower() == "true"
    except Exception:
        return False


def _git_is_dirty(repo_root: Path) -> bool:
    try:
        p = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        return p.returncode == 0 and bool((p.stdout or "").strip())
    except Exception:
        return False


def _git_ref_exists(repo_root: Path, ref: str) -> bool:
    try:
        p = subprocess.run(
            ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        return p.returncode == 0
    except Exception:
        return False


def _git_show_bytes(repo_root: Path, ref: str, rel_path: str) -> bytes | None:
    # Never print file content; we only use it for deterministic line counts.
    try:
        p = subprocess.run(
            ["git", "show", f"{ref}:{rel_path}"],
            cwd=repo_root,
            capture_output=True,
            check=False,
        )
        if p.returncode != 0:
            return None
        return p.stdout
    except Exception:
        return None


def _iter_tracked_python_files(repo_root: Path) -> list[str]:
    excluded_prefixes = (
        ".venv/",
        ".cache/",
        "evidence/",
        "dist/",
        "autonomous_orchestrator.egg-info/",
    )

    if _is_git_work_tree(repo_root):
        p = subprocess.run(
            ["git", "ls-files", "--", "*.py"],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        if p.returncode == 0:
            paths = []
            for line in (p.stdout or "").splitlines():
                rel = line.strip()
                if not rel:
                    continue
                if any(rel.startswith(prefix) for prefix in excluded_prefixes):
                    continue
                paths.append(rel)
            return sorted(set(paths))

    # Fallback when git isn't available (best-effort, deterministic).
    excluded_dirnames = {".venv", ".cache", "evidence", "dist", "autonomous_orchestrator.egg-info"}
    out: list[str] = []
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in sorted(dirs) if d not in excluded_dirnames]
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            abs_path = Path(root) / name
            try:
                rel = abs_path.resolve().relative_to(repo_root.resolve()).as_posix()
            except Exception:
                continue
            if any(rel.startswith(prefix) for prefix in excluded_prefixes):
                continue
            out.append(rel)
    return sorted(set(out))


class _FunctionVisitor(ast.NodeVisitor):
    def __init__(self, *, source_path: str):
        self._stack: list[str] = []
        self.functions: list[dict[str, Any]] = []
        self._source_path = source_path

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()
        return None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self._record_function(node)
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()
        return None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self._record_function(node)
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()
        return None

    def _record_function(self, node: ast.AST) -> None:
        lineno = getattr(node, "lineno", None)
        end_lineno = getattr(node, "end_lineno", None)
        name = getattr(node, "name", None)
        if not isinstance(lineno, int) or not isinstance(end_lineno, int) or not isinstance(name, str):
            return
        lines = int(end_lineno - lineno + 1)
        qualname = ".".join([*self._stack, name]) if self._stack else name
        self.functions.append(
            {
                "path": self._source_path,
                "qualname": qualname,
                "start_line": lineno,
                "end_line": end_lineno,
                "lines": lines,
            }
        )


def _parse_config(obj: Any) -> ScriptBudgetConfig:
    if not isinstance(obj, dict):
        raise ValueError("CONFIG_INVALID: root must be an object")
    if obj.get("version") != "v1":
        raise ValueError("CONFIG_INVALID: version must be v1")

    raw_py_limits = obj.get("python_file_limits")
    if not isinstance(raw_py_limits, dict):
        raise ValueError("CONFIG_INVALID: python_file_limits must be an object")
    py_soft = raw_py_limits.get("soft_lines")
    py_hard = raw_py_limits.get("hard_lines")
    if not isinstance(py_soft, int) or not isinstance(py_hard, int) or py_soft < 0 or py_hard < 0:
        raise ValueError("CONFIG_INVALID: python_file_limits soft_lines/hard_lines must be non-negative integers")
    py_limits = PythonFileLimits(soft_lines=int(py_soft), hard_lines=int(py_hard))

    raw_gf = obj.get("grandfathered_files")
    if not isinstance(raw_gf, list):
        raise ValueError("CONFIG_INVALID: grandfathered_files must be a list")
    grandfathered: dict[str, GrandfatheredFile] = {}
    for item in raw_gf:
        if not isinstance(item, dict):
            raise ValueError("CONFIG_INVALID: grandfathered_files entries must be objects")
        path = item.get("path")
        mode = item.get("mode") if isinstance(item.get("mode"), str) else "baseline_ref"
        current_lines = item.get("current_lines")
        max_allowed = item.get("max_allowed_lines")
        if not isinstance(path, str) or not path.strip():
            raise ValueError("CONFIG_INVALID: grandfathered_files.path must be non-empty string")
        if mode not in {"baseline_ref", "no_growth_only"}:
            raise ValueError("CONFIG_INVALID: grandfathered_files.mode must be baseline_ref|no_growth_only")
        if not isinstance(current_lines, int) or current_lines < 0:
            raise ValueError("CONFIG_INVALID: grandfathered_files.current_lines must be a non-negative integer")
        if not isinstance(max_allowed, int) or max_allowed < 0:
            raise ValueError("CONFIG_INVALID: grandfathered_files.max_allowed_lines must be a non-negative integer")

        expires_on = item.get("expires_on")
        if expires_on is not None and not isinstance(expires_on, str):
            raise ValueError("CONFIG_INVALID: grandfathered_files.expires_on must be string|null")
        target_soft = item.get("target_soft")
        if target_soft is not None and (not isinstance(target_soft, int) or target_soft < 0):
            raise ValueError("CONFIG_INVALID: grandfathered_files.target_soft must be int|null (>=0)")
        target_hard = item.get("target_hard")
        if target_hard is not None and (not isinstance(target_hard, int) or target_hard < 0):
            raise ValueError("CONFIG_INVALID: grandfathered_files.target_hard must be int|null (>=0)")

        grandfathered[path] = GrandfatheredFile(
            path=path,
            mode=mode,
            current_lines=int(current_lines),
            max_allowed_lines=int(max_allowed),
            expires_on=str(expires_on) if isinstance(expires_on, str) else None,
            target_soft=int(target_soft) if isinstance(target_soft, int) else None,
            target_hard=int(target_hard) if isinstance(target_hard, int) else None,
        )

    raw_file_limits = obj.get("file_line_limits")
    if not isinstance(raw_file_limits, list) or not raw_file_limits:
        raise ValueError("CONFIG_INVALID: file_line_limits must be a non-empty list")

    file_limits: list[FileLineLimit] = []
    for item in raw_file_limits:
        if not isinstance(item, dict):
            raise ValueError("CONFIG_INVALID: file_line_limits entries must be objects")
        path = item.get("path")
        soft = item.get("soft")
        hard = item.get("hard")
        if not isinstance(path, str) or not path.strip():
            raise ValueError("CONFIG_INVALID: file_line_limits.path must be non-empty string")
        if not isinstance(soft, int) or not isinstance(hard, int) or soft < 0 or hard < 0:
            raise ValueError("CONFIG_INVALID: file_line_limits soft/hard must be non-negative integers")
        file_limits.append(FileLineLimit(path=path, soft=int(soft), hard=int(hard)))

    raw_func_limits = obj.get("function_line_limits")
    if not isinstance(raw_func_limits, dict):
        raise ValueError("CONFIG_INVALID: function_line_limits must be an object")
    soft_f = raw_func_limits.get("soft")
    hard_f = raw_func_limits.get("hard")
    if not isinstance(soft_f, int) or not isinstance(hard_f, int) or soft_f < 0 or hard_f < 0:
        raise ValueError("CONFIG_INVALID: function_line_limits soft/hard must be non-negative integers")

    raw_scan_paths = obj.get("function_scan_paths")
    if not isinstance(raw_scan_paths, list) or not raw_scan_paths:
        raise ValueError("CONFIG_INVALID: function_scan_paths must be a non-empty list")
    scan_paths: list[str] = []
    for p in raw_scan_paths:
        if not isinstance(p, str) or not p.strip():
            raise ValueError("CONFIG_INVALID: function_scan_paths entries must be non-empty strings")
        scan_paths.append(p)

    return ScriptBudgetConfig(
        python_file_limits=py_limits,
        grandfathered_files=grandfathered,
        file_line_limits=file_limits,
        function_line_limits=FunctionLineLimits(soft=int(soft_f), hard=int(hard_f)),
        function_scan_paths=scan_paths,
    )


def _status_from_violations(
    *,
    exceeded_soft: list[dict[str, Any]],
    exceeded_hard: list[dict[str, Any]],
    function_soft: list[dict[str, Any]],
    function_hard: list[dict[str, Any]],
) -> str:
    if exceeded_hard or function_hard:
        return "FAIL"
    if exceeded_soft or function_soft:
        return "WARN"
    return "OK"


def _write_github_step_summary(report: dict[str, Any]) -> None:
    if (os.environ.get("GITHUB_ACTIONS") or "").strip().lower() != "true":
        return
    summary_path = (os.environ.get("GITHUB_STEP_SUMMARY") or "").strip()
    if not summary_path:
        return

    status = str(report.get("status", "OK"))
    exceeded_soft = report.get("exceeded_soft") if isinstance(report.get("exceeded_soft"), list) else []
    exceeded_hard = report.get("exceeded_hard") if isinstance(report.get("exceeded_hard"), list) else []
    function_soft = report.get("function_soft") if isinstance(report.get("function_soft"), list) else []
    function_hard = report.get("function_hard") if isinstance(report.get("function_hard"), list) else []

    def fmt_file(item: dict[str, Any]) -> str:
        return f"{item.get('path')} lines={item.get('lines')} soft={item.get('soft')} hard={item.get('hard')}"

    def fmt_func(item: dict[str, Any]) -> str:
        return (
            f"{item.get('path')}::{item.get('qualname')} "
            f"lines={item.get('lines')} soft={item.get('soft')} hard={item.get('hard')}"
        )

    offenders: list[str] = []
    offenders.extend([fmt_file(x) for x in exceeded_hard[:5]])
    offenders.extend([fmt_func(x) for x in function_hard[:5]])
    offenders.extend([fmt_file(x) for x in exceeded_soft[:5]])
    offenders.extend([fmt_func(x) for x in function_soft[:5]])
    offenders = offenders[:5]

    lines: list[str] = []
    lines.append("### Script Budget")
    lines.append(f"- status: **{status}**")
    lines.append(
        "- counts: "
        + f"file_hard={len(exceeded_hard)} file_soft={len(exceeded_soft)} "
        + f"fn_hard={len(function_hard)} fn_soft={len(function_soft)}"
    )
    if offenders:
        lines.append("")
        lines.append("Top offenders (max 5):")
        for o in offenders:
            lines.append(f"- `{o}`")
    lines.append("")
    lines.append("Recommendation: split large scripts into smaller modules (e.g. `commands/*` or `smoke/*`).")

    top_py = report.get("top_largest_py") if isinstance(report.get("top_largest_py"), list) else []
    if top_py:
        lines.append("")
        lines.append("Top 5 largest `*.py` files:")
        for item in top_py[:5]:
            if not isinstance(item, dict):
                continue
            lines.append(f"- `{item.get('path')}` lines={item.get('lines')}")

    gf_growth = report.get("grandfathered_growth_check") if isinstance(report.get("grandfathered_growth_check"), list) else []
    grew = []
    for item in gf_growth:
        if isinstance(item, dict) and item.get("status") == "GROWN":
            grew.append(item)
    if gf_growth:
        lines.append("")
        lines.append(f"Grandfathered growth check: total={len(gf_growth)} grew={len(grew)}")
        for item in grew[:5]:
            path = item.get("path")
            cur = item.get("current_lines")
            base = item.get("baseline_lines")
            lines.append(f"- `{path}` current={cur} baseline={base} (**GROWN**)")  # no secrets

    try:
        Path(summary_path).write_text("\n".join(lines) + "\n", encoding="utf-8", append=True)  # type: ignore[arg-type]
    except TypeError:
        # Python <3.11 doesn't support Path.write_text(append=...); use open.
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(prog="check_script_budget", description="Deterministic script budget guardrails (soft=warn, hard=fail).")
    ap.add_argument("--config", default="ci/script_budget.v1.json")
    ap.add_argument("--out", default=".cache/script_budget/report.json")
    ap.add_argument("--baseline-ref", default="HEAD~1", help="Git ref used for grandfathered no-growth checks (default: HEAD~1).")
    args = ap.parse_args()

    repo_root = _repo_root()
    out_path = _require_relative_to_root(repo_root, str(args.out))
    out_path.parent.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "status": "FAIL",
        "exceeded_soft": [],
        "exceeded_hard": [],
        "function_soft": [],
        "function_hard": [],
    }

    try:
        config_path = _require_relative_to_root(repo_root, str(args.config))
        config_obj = _load_json(config_path)
        cfg = _parse_config(config_obj)
        file_limits = cfg.file_line_limits
        func_limits = cfg.function_line_limits
        scan_paths = cfg.function_scan_paths
        py_limits = cfg.python_file_limits
        grandfathered = cfg.grandfathered_files
        baseline_ref = str(getattr(args, "baseline_ref", "HEAD~1") or "HEAD~1")

        exceeded_soft: list[dict[str, Any]] = []
        exceeded_hard: list[dict[str, Any]] = []

        explicit_paths = {fl.path for fl in file_limits}

        for fl in sorted(file_limits, key=lambda x: x.path):
            abs_path = _require_relative_to_root(repo_root, fl.path)
            if not abs_path.exists():
                exceeded_hard.append(
                    {
                        "path": fl.path,
                        "lines": None,
                        "soft": fl.soft,
                        "hard": fl.hard,
                        "error": "FILE_MISSING",
                    }
                )
                continue
            lines = _count_lines(abs_path)
            entry = {"path": fl.path, "lines": lines, "soft": fl.soft, "hard": fl.hard}
            if lines > fl.hard:
                exceeded_hard.append(entry)
            elif lines > fl.soft:
                exceeded_soft.append(entry)

        # Global Python file budgets (all tracked *.py, with grandfathering + no-growth checks).
        python_paths = _iter_tracked_python_files(repo_root)
        python_line_counts: dict[str, int] = {}
        for rel in python_paths:
            abs_path = _require_relative_to_root(repo_root, rel)
            if not abs_path.exists():
                python_line_counts[rel] = -1
                continue
            python_line_counts[rel] = _count_lines(abs_path)

        top_largest_py: list[dict[str, Any]] = []
        for rel, lines in sorted(python_line_counts.items(), key=lambda kv: (-int(kv[1]), str(kv[0]))):
            if lines < 0:
                continue
            top_largest_py.append({"path": rel, "lines": lines})
            if len(top_largest_py) >= 10:
                break

        in_git = _is_git_work_tree(repo_root)
        dirty = _git_is_dirty(repo_root) if in_git else False
        baseline_ok = in_git and not dirty and _git_ref_exists(repo_root, baseline_ref)

        grandfathered_growth_check: list[dict[str, Any]] = []

        python_ok = 0
        python_warn = 0
        python_fail = 0

        for rel in sorted(python_paths):
            # Explicit per-file budgets already handled above.
            if rel in explicit_paths:
                # Still contribute to counts using the explicit budgets.
                fl = next((x for x in file_limits if x.path == rel), None)
                lines = python_line_counts.get(rel, -1)
                if lines < 0 or fl is None:
                    python_fail += 1
                elif lines > fl.hard:
                    python_fail += 1
                elif lines > fl.soft:
                    python_warn += 1
                else:
                    python_ok += 1
                continue

            lines = python_line_counts.get(rel, -1)
            soft = py_limits.soft_lines
            hard = py_limits.hard_lines
            if lines < 0:
                python_fail += 1
                exceeded_hard.append({"path": rel, "lines": None, "soft": soft, "hard": hard, "error": "FILE_MISSING"})
                continue

            gf = grandfathered.get(rel)
            if gf is not None:
                baseline_lines: int | None = None
                baseline_ref_label = baseline_ref
                growth_status = "SKIPPED_NO_GIT"
                delta_lines: int | None = None
                if gf.mode == "no_growth_only":
                    baseline_lines = gf.current_lines
                    baseline_ref_label = "PINNED"
                    delta_lines = int(lines) - int(baseline_lines)
                    growth_status = "OK" if delta_lines == 0 else "GROWN"
                    if delta_lines != 0:
                        exceeded_hard.append(
                            {
                                "path": rel,
                                "lines": lines,
                                "soft": soft,
                                "hard": hard,
                                "error_code": "PY_FILE_NO_GROWTH",
                                "baseline_ref": "PINNED",
                                "baseline_lines": baseline_lines,
                                "delta_lines": delta_lines,
                            }
                        )
                        python_fail += 1
                    else:
                        python_ok += 1
                else:
                    if baseline_ok:
                        baseline_bytes = _git_show_bytes(repo_root, baseline_ref, rel)
                        baseline_lines = _count_lines_from_bytes(baseline_bytes) if baseline_bytes is not None else lines
                        growth_status = "OK"
                        if baseline_lines is not None and lines > baseline_lines:
                            growth_status = "GROWN"
                            exceeded_hard.append(
                                {
                                    "path": rel,
                                    "lines": lines,
                                    "soft": soft,
                                    "hard": hard,
                                    "error_code": "PY_FILE_GROWTH_FORBIDDEN",
                                    "baseline_ref": baseline_ref,
                                    "baseline_lines": baseline_lines,
                                }
                            )

                    elif in_git and dirty:
                        growth_status = "SKIPPED_DIRTY_WORKTREE"
                    elif in_git and not _git_ref_exists(repo_root, baseline_ref):
                        growth_status = "SKIPPED_BASELINE_REF_MISSING"

                grandfathered_growth_check.append(
                    {
                        "path": rel,
                        "mode": gf.mode,
                        "current_lines": lines,
                        "baseline_ref": baseline_ref_label,
                        "baseline_lines": baseline_lines,
                        "delta_lines": delta_lines,
                        "status": growth_status,
                        "max_allowed_lines": gf.max_allowed_lines,
                    }
                )

                if gf.mode != "no_growth_only":
                    if growth_status == "GROWN":
                        python_fail += 1
                    else:
                        # Oversized but allowed (no-growth enforced via baseline check).
                        if lines > hard:
                            python_warn += 1
                            exceeded_soft.append({"path": rel, "lines": lines, "soft": soft, "hard": hard, "error": "GRANDFATHERED"})
                        else:
                            python_ok += 1
                continue

            # Normal Python file budgets.
            if lines > hard:
                python_fail += 1
                exceeded_hard.append({"path": rel, "lines": lines, "soft": soft, "hard": hard})
            elif lines > soft:
                python_warn += 1
                exceeded_soft.append({"path": rel, "lines": lines, "soft": soft, "hard": hard})
            else:
                python_ok += 1

        function_soft: list[dict[str, Any]] = []
        function_hard: list[dict[str, Any]] = []

        for rel in sorted(set(scan_paths)):
            abs_path = _require_relative_to_root(repo_root, rel)
            if not abs_path.exists():
                function_hard.append(
                    {
                        "path": rel,
                        "qualname": None,
                        "start_line": None,
                        "end_line": None,
                        "lines": None,
                        "soft": func_limits.soft,
                        "hard": func_limits.hard,
                        "error": "FILE_MISSING",
                    }
                )
                continue
            if abs_path.suffix.lower() != ".py":
                continue
            try:
                src = abs_path.read_text(encoding="utf-8")
                tree = ast.parse(src)
            except Exception:
                function_hard.append(
                    {
                        "path": rel,
                        "qualname": None,
                        "start_line": None,
                        "end_line": None,
                        "lines": None,
                        "soft": func_limits.soft,
                        "hard": func_limits.hard,
                        "error": "PARSE_FAILED",
                    }
                )
                continue

            v = _FunctionVisitor(source_path=rel)
            v.visit(tree)
            for fn in v.functions:
                lines = int(fn.get("lines") or 0)
                entry = dict(fn)
                entry["soft"] = func_limits.soft
                entry["hard"] = func_limits.hard
                if lines > func_limits.hard:
                    function_hard.append(entry)
                elif lines > func_limits.soft:
                    function_soft.append(entry)

        exceeded_soft.sort(key=lambda x: (str(x.get("path")), int(x.get("lines") or 0)))
        exceeded_hard.sort(key=lambda x: (str(x.get("path")), int(x.get("lines") or 0)))
        function_soft.sort(key=lambda x: (str(x.get("path")), str(x.get("qualname") or ""), int(x.get("lines") or 0)))
        function_hard.sort(key=lambda x: (str(x.get("path")), str(x.get("qualname") or ""), int(x.get("lines") or 0)))

        status = _status_from_violations(
            exceeded_soft=exceeded_soft,
            exceeded_hard=exceeded_hard,
            function_soft=function_soft,
            function_hard=function_hard,
        )

        report = {
            "status": status,
            "exceeded_soft": exceeded_soft,
            "exceeded_hard": exceeded_hard,
            "function_soft": function_soft,
            "function_hard": function_hard,
            "python_budget_summary": {
                "total": len(python_paths),
                "ok": python_ok,
                "warn": python_warn,
                "fail": python_fail,
                "soft_lines": py_limits.soft_lines,
                "hard_lines": py_limits.hard_lines,
            },
            "top_largest_py": top_largest_py,
            "grandfathered_growth_check": sorted(grandfathered_growth_check, key=lambda x: str(x.get("path") or "")),
            "baseline_ref_used": baseline_ref,
            "git": {"available": in_git, "dirty": dirty, "baseline_ref_exists": bool(baseline_ok)},
        }
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        _write_github_step_summary(report)

        soft_total = len(exceeded_soft) + len(function_soft)
        hard_total = len(exceeded_hard) + len(function_hard)
        print(f"SCRIPT_BUDGET status={status} hard_exceeded={hard_total} soft_exceeded={soft_total} out={out_path.as_posix()}")

        return 1 if status == "FAIL" else 0
    except Exception as e:
        report = {
            "status": "FAIL",
            "exceeded_soft": [],
            "exceeded_hard": [],
            "function_soft": [],
            "function_hard": [],
            "error": str(e)[:300],
        }
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        _write_github_step_summary(report)
        print("SCRIPT_BUDGET status=FAIL hard_exceeded=0 soft_exceeded=0 out=" + out_path.as_posix())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

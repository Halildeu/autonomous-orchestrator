from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _match_any(name: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in patterns)


def _git_available(repo_root: Path) -> bool:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=repo_root,
            text=True,
            capture_output=True,
        )
        return proc.returncode == 0 and proc.stdout.strip() == "true"
    except Exception:
        return False


def _git_tracked(repo_root: Path) -> set[str]:
    proc = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        return set()
    return {p for p in proc.stdout.split("\0") if p}


def _git_untracked(repo_root: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z"],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        return []
    entries = [e for e in proc.stdout.split("\0") if e]
    untracked: list[str] = []
    for entry in entries:
        if entry.startswith("?? "):
            untracked.append(entry[3:])
    return untracked


def _validate_layout(layout_path: Path, schema_path: Path) -> dict[str, Any]:
    layout = _load_json(layout_path)
    schema = _load_json(schema_path)
    Draft202012Validator(schema).validate(layout)
    return layout if isinstance(layout, dict) else {}


def _ambiguous_dir_findings(repo_root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    modules_dir = repo_root / "modules"
    src_modules_dir = repo_root / "src" / "modules"
    if modules_dir.exists() and src_modules_dir.exists():
        findings.append(
            {
                "kind": "AMBIGUOUS_DIR",
                "path": "modules",
                "severity": "INFO",
                "hint": "Ensure docs explain usage vs src/modules.",
            }
        )
    return findings


def _make_findings(
    *,
    repo_root: Path,
    layout: dict[str, Any],
    git_tracked: set[str],
    git_untracked: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    allowed_dirs = {str(x) for x in layout.get("allowed_top_level_dirs", []) if isinstance(x, str)}
    allowed_files = {str(x) for x in layout.get("allowed_top_level_files", []) if isinstance(x, str)}
    generated_dirs = [str(x) for x in layout.get("generated_dirs", []) if isinstance(x, str)]
    generated_files = [str(x) for x in layout.get("generated_files_patterns", []) if isinstance(x, str)]

    report_patterns = ["sim_report*.json", "reaper_report*.json"]
    root_dirs = sorted([p for p in repo_root.iterdir() if p.is_dir()], key=lambda p: p.name)
    root_files = sorted([p for p in repo_root.iterdir() if p.is_file()], key=lambda p: p.name)

    findings: list[dict[str, Any]] = []
    suggestions: list[dict[str, Any]] = []

    for d in root_dirs:
        name = d.name
        if name in allowed_dirs:
            continue
        if _match_any(name, generated_dirs):
            continue
        if name == ".git":
            continue
        findings.append(
            {
                "kind": "UNEXPECTED_DIR",
                "path": name,
                "severity": "WARN",
                "hint": "Add to SSOT or remove (manual).",
            }
        )

    for f in root_files:
        name = f.name
        if name in allowed_files:
            continue
        if _match_any(name, generated_files):
            if _match_any(name, report_patterns):
                findings.append(
                    {
                        "kind": "ROOT_REPORT_FILE",
                        "path": name,
                        "severity": "WARN",
                        "hint": "Move to .cache/reports via CHG suggestion (manual).",
                    }
                )
                suggestions.append(
                    {
                        "change_id": sha256(f"MOVE:{name}".encode("utf-8")).hexdigest()[:16],
                        "kind": "MOVE_SUGGESTION",
                        "from": name,
                        "to": f".cache/reports/{name}",
                        "apply": "manual",
                    }
                )
            continue
        findings.append(
            {
                "kind": "UNEXPECTED_FILE",
                "path": name,
                "severity": "WARN",
                "hint": "Add to SSOT or ignore; do not auto-delete.",
            }
        )

    findings.extend(_ambiguous_dir_findings(repo_root))

    if git_tracked or git_untracked:
        tracked_generated: set[str] = set()
        for path in git_tracked:
            top = path.split("/", 1)[0]
            if _match_any(top, generated_dirs):
                tracked_generated.add(top)
            if "/" not in path and _match_any(path, generated_files):
                tracked_generated.add(path)
        for entry in sorted(tracked_generated):
            findings.append(
                {
                    "kind": "TRACKED_GENERATED",
                    "path": entry,
                    "severity": "WARN",
                    "hint": "Should be git-ignored; do not auto-delete.",
                }
            )

        untracked_generated: set[str] = set()
        for path in git_untracked:
            top = path.split("/", 1)[0]
            if _match_any(top, generated_dirs):
                untracked_generated.add(top)
            if "/" not in path and _match_any(path, generated_files):
                untracked_generated.add(path)
        for entry in sorted(untracked_generated):
            findings.append(
                {
                    "kind": "UNTRACKED_GENERATED",
                    "path": entry,
                    "severity": "WARN",
                    "hint": "Local generated artifact; keep ignored.",
                }
            )

    findings.sort(key=lambda f: (str(f.get("kind") or ""), str(f.get("path") or "")))
    suggestions.sort(key=lambda s: (str(s.get("from") or ""), str(s.get("to") or "")))
    return findings, suggestions


def _write_change_proposal(
    *,
    repo_root: Path,
    suggestions: list[dict[str, Any]],
) -> Path | None:
    if not suggestions:
        return None
    changes_dir = repo_root / "roadmaps" / "SSOT" / "changes"
    changes_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    existing = sorted(changes_dir.glob(f"CHG-{date_str}-*.json"))
    next_idx = 1
    for path in existing:
        suffix = path.stem.split("-")[-1]
        if suffix.isdigit():
            next_idx = max(next_idx, int(suffix) + 1)
    change_id = f"CHG-{date_str}-{next_idx:03d}"

    move_lines = [f"- move {s['from']} -> {s['to']}" for s in suggestions if isinstance(s, dict)]
    note = "Repo hygiene: move root report files into .cache/reports and keep them ignored.\n" + "\n".join(move_lines)

    payload = {
        "change_id": change_id,
        "version": "v1",
        "type": "modify",
        "risk_level": "low",
        "target": {"milestone_id": "M0"},
        "rationale": "Repo hygiene suggests moving generated root reports into .cache/ to reduce clutter.",
        "patches": [
            {
                "op": "append_milestone_note",
                "milestone_id": "M0",
                "note": note,
            }
        ],
        "gates": ["python ci/validate_schemas.py"],
    }

    out_path = changes_dir / f"{change_id}.json"
    out_path.write_text(_dump_json(payload), encoding="utf-8")
    return out_path


def run_repo_hygiene(
    *,
    repo_root: Path,
    layout_path: Path,
    out_path: Path | None,
    mode: str,
) -> dict[str, Any]:
    schema_path = repo_root / "schemas" / "repo-layout.schema.json"
    if not schema_path.exists():
        return {"status": "FAIL", "error_code": "SCHEMA_MISSING"}
    if not layout_path.exists():
        return {"status": "FAIL", "error_code": "LAYOUT_MISSING"}

    try:
        layout = _validate_layout(layout_path, schema_path)
    except Exception as e:
        return {"status": "FAIL", "error_code": "SCHEMA_INVALID", "message": str(e)[:200]}

    git_ok = _git_available(repo_root)
    tracked = _git_tracked(repo_root) if git_ok else set()
    untracked = _git_untracked(repo_root) if git_ok else []

    findings, suggestions = _make_findings(
        repo_root=repo_root,
        layout=layout,
        git_tracked=tracked,
        git_untracked=untracked,
    )

    unexpected_dirs = sum(1 for f in findings if f.get("kind") == "UNEXPECTED_DIR")
    generated_top_dirs = 0
    generated_dirs = [str(x) for x in layout.get("generated_dirs", []) if isinstance(x, str)]
    for d in sorted([p for p in repo_root.iterdir() if p.is_dir()], key=lambda p: p.name):
        if _match_any(d.name, generated_dirs):
            generated_top_dirs += 1

    tracked_generated = sum(1 for f in findings if f.get("kind") == "TRACKED_GENERATED")
    untracked_generated_dirs = 0
    if untracked:
        for d in sorted([p for p in repo_root.iterdir() if p.is_dir()], key=lambda p: p.name):
            if _match_any(d.name, generated_dirs):
                if any(p == d.name or p.startswith(d.name + "/") for p in untracked):
                    untracked_generated_dirs += 1

    status = "WARN" if findings else "OK"

    report = {
        "version": "v1",
        "repo_root": ".",
        "layout_version": str(layout.get("version", "v1")),
        "status": status,
        "summary": {
            "unexpected_top_level_dirs": int(unexpected_dirs),
            "generated_top_level_dirs_present": int(generated_top_dirs),
            "tracked_generated_files": int(tracked_generated),
            "untracked_generated_dirs": int(untracked_generated_dirs),
        },
        "findings": findings,
        "suggested_changes": suggestions,
    }

    if mode == "suggest" and suggestions:
        chg_path = _write_change_proposal(repo_root=repo_root, suggestions=suggestions)
        if chg_path is not None:
            report["suggested_changes"].append(
                {
                    "change_id": chg_path.stem,
                    "kind": "CHG_DRAFT",
                    "from": str(layout_path),
                    "to": str(chg_path.relative_to(repo_root)),
                    "apply": "manual",
                }
            )
            report["suggested_changes"].sort(key=lambda s: (str(s.get("from") or ""), str(s.get("to") or "")))

    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(_dump_json(report), encoding="utf-8")

    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.ops.repo_hygiene", add_help=True)
    ap.add_argument("--mode", default="report", choices=["report", "suggest"])
    ap.add_argument("--layout", default="docs/OPERATIONS/repo-layout.v1.json")
    ap.add_argument("--out", default=".cache/repo_hygiene/report.json")
    args = ap.parse_args(argv)

    root = _repo_root()
    layout_path = Path(str(args.layout))
    if not layout_path.is_absolute():
        layout_path = root / layout_path
    layout_path = layout_path.resolve()
    out_path = Path(str(args.out))
    if not out_path.is_absolute():
        out_path = root / out_path
    out_path = out_path.resolve()

    res = run_repo_hygiene(repo_root=root, layout_path=layout_path, out_path=out_path, mode=str(args.mode))
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") in {"OK", "WARN"} else 2


if __name__ == "__main__":
    raise SystemExit(main())

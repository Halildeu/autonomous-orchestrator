from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


TEST_SUFFIXES = ("_contract_test.py", "_test.py")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    return parser.parse_args(argv)


def _family_key(path: Path, src_root: Path) -> str:
    rel = path.relative_to(src_root)
    parts = rel.parts
    return parts[0] if parts else "src"


def _is_test(path: Path) -> bool:
    return path.name.endswith(TEST_SUFFIXES)


def _render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Coverage Visibility (report-only)",
        "",
        f"status={payload['status']}",
        f"visibility_mode={payload['visibility_mode']}",
        f"families_total={payload['totals']['families_total']}",
        f"families_with_tests={payload['totals']['families_with_tests']}",
        f"code_files_total={payload['totals']['code_files_total']}",
        f"test_files_total={payload['totals']['test_files_total']}",
        "",
        "| family | code_files | test_files | status |",
        "|---|---:|---:|---|",
    ]
    for row in payload["families"]:
        lines.append(f"| {row['family']} | {row['code_files']} | {row['test_files']} | {row['status']} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = Path(args.repo_root).expanduser().resolve()
    src_root = repo_root / "src"
    family_map: dict[str, dict[str, Any]] = {}
    for path in sorted(src_root.rglob("*.py")):
        family = _family_key(path, src_root)
        bucket = family_map.setdefault(
            family,
            {"family": family, "code_files": 0, "test_files": 0, "test_paths": []},
        )
        if path.name == "__init__.py":
            continue
        if _is_test(path):
            bucket["test_files"] += 1
            bucket["test_paths"].append(path.relative_to(repo_root).as_posix())
        else:
            bucket["code_files"] += 1

    families = []
    totals = {
        "families_total": 0,
        "families_with_tests": 0,
        "code_files_total": 0,
        "test_files_total": 0,
    }
    for family in sorted(family_map):
        row = family_map[family]
        if row["code_files"] == 0:
            continue
        status = "OK" if row["test_files"] > 0 else "WARN"
        families.append(
            {
                "family": family,
                "code_files": row["code_files"],
                "test_files": row["test_files"],
                "status": status,
                "sample_tests": row["test_paths"][:5],
            }
        )
        totals["families_total"] += 1
        totals["code_files_total"] += row["code_files"]
        totals["test_files_total"] += row["test_files"]
        if row["test_files"] > 0:
            totals["families_with_tests"] += 1

    payload = {
        "version": "v1",
        "kind": "coverage-visibility-report",
        "status": "OK" if totals["families_total"] == totals["families_with_tests"] else "WARN",
        "visibility_mode": "structural_report_only",
        "repo_root": repo_root.as_posix(),
        "families": families,
        "totals": totals,
        "notes": [
            "Bu rapor line coverage gate degil; src/ aile bazli test gorunurlugu raporudur.",
            "Bir sonraki faz: line coverage aracini report-only olarak eklemek.",
        ],
    }
    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(_render_md(payload), encoding="utf-8")
    print(json.dumps({"status": "OK", "out_json": out_json.as_posix(), "out_md": out_md.as_posix()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

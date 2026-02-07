from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from src.roadmap.sanitize import scan_directory


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _validate_chg(core_root: Path, chg: dict[str, Any]) -> list[str]:
    schema_path = core_root / "schemas" / "chg-debt.schema.json"
    if not schema_path.exists():
        return ["SCHEMA_MISSING"]
    schema = _load_json(schema_path)
    Draft202012Validator(schema).validate(chg)
    return []


def _safe_relpath(rel: str) -> str:
    rel = Path(rel).as_posix()
    if rel.startswith("../") or rel.startswith("/") or rel.startswith("..\\"):
        raise ValueError("INVALID_PATH")
    return rel


def _build_content(chg_id: str, action: dict[str, Any]) -> str:
    note = action.get("note") if isinstance(action, dict) else None
    create = action.get("create") if isinstance(action, dict) else None
    patch = action.get("patch") if isinstance(action, dict) else None
    if isinstance(create, dict) and isinstance(create.get("content"), str):
        return create.get("content")
    if isinstance(note, dict) and isinstance(note.get("text"), str):
        return note.get("text")
    if isinstance(patch, dict):
        return "pattern: " + str(patch.get("pattern") or "") + "\nreplace: " + str(patch.get("replace") or "")
    return f"{chg_id} plan placeholder"


def _default_relpath(kind: str, chg_id: str) -> str:
    if kind == "ADD_IGNORE":
        return "patches/.gitignore.patch"
    if kind in {"REFACTOR_HINT", "FORMAT_FIX"}:
        return f"plans/{chg_id}.md"
    if kind == "TEMPLATE_ADD":
        return f"templates/{chg_id}.txt"
    return f"notes/{chg_id}.md"


def apply_debt_incubator(
    *,
    workspace_root: Path,
    chg_path: Path,
    dry_run: bool,
) -> dict[str, Any]:
    core_root = _repo_root()
    chg = _load_json(chg_path)
    if not isinstance(chg, dict):
        return {"status": "FAIL", "error_code": "CHG_INVALID"}
    errors = _validate_chg(core_root, chg)
    if errors:
        return {"status": "FAIL", "error_code": "CHG_SCHEMA_INVALID", "errors": errors[:3]}

    safety = chg.get("safety") if isinstance(chg.get("safety"), dict) else {}
    if safety.get("apply_scope") != "INCUBATOR_ONLY":
        return {"status": "FAIL", "error_code": "INVALID_APPLY_SCOPE"}
    if safety.get("destructive") is True:
        return {"status": "FAIL", "error_code": "DESTRUCTIVE_NOT_ALLOWED"}

    chg_id = str(chg.get("id") or "")
    actions = chg.get("actions") if isinstance(chg.get("actions"), list) else []
    if not actions:
        return {"status": "FAIL", "error_code": "NO_ACTIONS"}

    incubator_root = workspace_root / "incubator"
    paths: list[str] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        kind = str(action.get("kind") or "")
        rel = action.get("file_relpath")
        if not isinstance(rel, str) or not rel.strip():
            rel = _default_relpath(kind, chg_id)
        try:
            rel = _safe_relpath(rel)
        except ValueError:
            return {"status": "FAIL", "error_code": "INVALID_PATH"}
        target = incubator_root / rel
        paths.append(target.as_posix())

        if dry_run:
            continue

        content = _build_content(chg_id, action)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            existing = target.read_text(encoding="utf-8")
            if existing != content:
                return {"status": "FAIL", "error_code": "CONTENT_MISMATCH", "path": str(target)}
            continue
        target.write_text(content, encoding="utf-8")

    if dry_run:
        return {"status": "WOULD_APPLY", "chg_id": chg_id, "incubator_paths": paths}

    ok, findings = scan_directory(root=incubator_root)
    if not ok:
        return {
            "status": "FAIL",
            "error_code": "SANITIZE_VIOLATION",
            "findings": [f"{f.path}:{f.rule}" for f in findings][:10],
        }

    return {"status": "OK", "chg_id": chg_id, "incubator_paths": paths}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.ops.debt_apply_incubator", add_help=True)
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--chg", required=True)
    ap.add_argument("--dry-run", default="true")
    args = ap.parse_args(argv)

    ws_root = Path(str(args.workspace_root)).resolve()
    if not ws_root.exists():
        print(json.dumps({"status": "FAIL", "error_code": "WORKSPACE_ROOT_INVALID"}, ensure_ascii=False, sort_keys=True))
        return 2

    chg_path = Path(str(args.chg)).resolve()
    if not chg_path.exists():
        print(json.dumps({"status": "FAIL", "error_code": "CHG_NOT_FOUND"}, ensure_ascii=False, sort_keys=True))
        return 2

    dry = str(args.dry_run).strip().lower() in {"1", "true", "yes", "y", "on"}
    res = apply_debt_incubator(workspace_root=ws_root, chg_path=chg_path, dry_run=dry)
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") in {"OK", "WOULD_APPLY"} else 2


if __name__ == "__main__":
    raise SystemExit(main())

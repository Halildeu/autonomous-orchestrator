from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    ext_root = Path(__file__).resolve().parents[1]
    manifest_path = ext_root / "extension.manifest.v1.json"
    schema_path = repo_root / "schemas" / "extension-manifest.schema.v1.json"

    manifest = _load_json(manifest_path)
    schema = _load_json(schema_path)
    Draft202012Validator(schema).validate(manifest)

    required_refs = [
        "policies/policy_ux_catalog_enforcement.v1.json",
        "schemas/policy-ux-catalog-enforcement.schema.v1.json",
        "schemas/ux-catalog.schema.v1.json",
        "schemas/ux-blueprint.schema.v1.json",
        "schemas/ux-interaction-matrix.schema.v1.json",
        "extensions/PRJ-UX-NORTH-STAR/contract/ux_katalogu.final_lock.v1.json",
        "extensions/PRJ-UX-NORTH-STAR/contract/ux_change_map.v1.json",
        "extensions/PRJ-UX-NORTH-STAR/contract/check_ux_catalog_enforcement.py",
        "src/ops/north_star_ux_build.py",
    ]
    for rel in required_refs:
        if not (repo_root / rel).exists():
            raise SystemExit(f"contract_test failed: missing {rel}")

    print(json.dumps({"status": "OK", "extension_id": manifest.get("extension_id")}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

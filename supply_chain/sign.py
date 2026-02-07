from __future__ import annotations

import hmac
import json
import os
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

import tomllib


def iso_utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def sha256_hex(data: bytes) -> str:
    return sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_hex(path.read_bytes())


def sorted_relpaths(paths: list[Path], *, root: Path) -> list[str]:
    rels = [p.resolve().relative_to(root).as_posix() for p in paths]
    return sorted(rels)


def list_json_files(dir_path: Path) -> list[Path]:
    if not dir_path.exists():
        return []
    return [p for p in dir_path.glob("*.json") if p.is_file()]


def concat_sha256(files: list[Path]) -> str:
    h = sha256()
    for p in files:
        h.update(p.read_bytes())
    return h.hexdigest()


def compute_inputs(root: Path) -> dict[str, Any]:
    sbom_path = root / "supply_chain" / "sbom.v1.json"
    if not sbom_path.exists():
        raise FileNotFoundError(f"Missing SBOM: {sbom_path}")

    policies = sorted(list_json_files(root / "policies"), key=lambda p: p.as_posix())
    workflows = sorted(list_json_files(root / "workflows"), key=lambda p: p.as_posix())
    configs = sorted(
        (list_json_files(root / "registry") + list_json_files(root / "orchestrator")),
        key=lambda p: p.as_posix(),
    )

    return {
        "sbom": {"path": "supply_chain/sbom.v1.json", "sha256": sha256_file(sbom_path)},
        "policies": {
            "paths": sorted_relpaths(policies, root=root),
            "concat_sha256": concat_sha256(policies),
        },
        "workflows": {
            "paths": sorted_relpaths(workflows, root=root),
            "concat_sha256": concat_sha256(workflows),
        },
        "registry_orchestrator": {
            "paths": sorted_relpaths(configs, root=root),
            "concat_sha256": concat_sha256(configs),
        },
    }


def get_signing_key() -> bytes:
    raw = os.environ.get("SUPPLY_CHAIN_SIGNING_KEY")
    if raw is None or not raw.strip():
        raw = "DEV_KEY"
    return raw.encode("utf-8")

def read_project_from_pyproject(pyproject_path: Path) -> dict[str, str]:
    if not pyproject_path.exists():
        return {"name": "unknown", "version": "unknown"}
    try:
        with pyproject_path.open("rb") as f:
            obj = tomllib.load(f)
    except Exception:
        return {"name": "unknown", "version": "unknown"}
    if not isinstance(obj, dict):
        return {"name": "unknown", "version": "unknown"}
    proj = obj.get("project") if isinstance(obj.get("project"), dict) else {}
    name = proj.get("name") if isinstance(proj.get("name"), str) and proj.get("name") else "unknown"
    version = proj.get("version") if isinstance(proj.get("version"), str) and proj.get("version") else "unknown"
    return {"name": name, "version": version}


def main() -> None:
    root = repo_root()
    out_dir = root / "supply_chain"
    out_dir.mkdir(parents=True, exist_ok=True)
    sig_path = out_dir / "signature.v1.json"

    inputs = compute_inputs(root)
    payload = json.dumps(inputs, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    key = get_signing_key()
    signature_hex = hmac.new(key, payload, sha256).hexdigest()

    project = read_project_from_pyproject(root / "pyproject.toml")

    record = {
        "algo": "HMAC-SHA256",
        "version": "v1",
        "signed_at": iso_utc_now(),
        "project": project,
        "inputs": inputs,
        "signature": signature_hex,
    }
    sig_path.write_text(json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {"status": "OK", "signature_path": str(sig_path), "signature_prefix": signature_hex[:12]},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    sys.exit(main())

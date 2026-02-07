from __future__ import annotations

import hmac
import json
import os
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def is_ci() -> bool:
    return (os.environ.get("GITHUB_ACTIONS") == "true") or (os.environ.get("CI") == "true")


def fail(error_code: str, message: str, *, details: dict[str, Any] | None = None) -> int:
    payload: dict[str, Any] = {"status": "ERROR", "error_code": error_code, "message": message}
    if details:
        payload.update(details)
    print(json.dumps(payload, ensure_ascii=False))
    return 1


def sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def list_json_files(dir_path: Path) -> list[Path]:
    if not dir_path.exists():
        return []
    return [p for p in dir_path.glob("*.json") if p.is_file()]


def sorted_relpaths(paths: list[Path], *, root: Path) -> list[str]:
    rels = [p.resolve().relative_to(root).as_posix() for p in paths]
    return sorted(rels)


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


def get_signing_key() -> bytes | None:
    raw = os.environ.get("SUPPLY_CHAIN_SIGNING_KEY")
    if raw is None or not raw.strip():
        if is_ci():
            return None
        raw = "DEV_KEY"
    return raw.encode("utf-8")


def main() -> int:
    root = repo_root()
    sig_path = root / "supply_chain" / "signature.v1.json"
    if not sig_path.exists():
        return fail("SIGNATURE_MISSING", "Missing supply_chain/signature.v1.json")

    try:
        record = json.loads(sig_path.read_text(encoding="utf-8"))
    except Exception as e:
        return fail("SIGNATURE_INVALID", "Failed to parse signature JSON.", details={"error": str(e)})

    if not isinstance(record, dict):
        return fail("SIGNATURE_INVALID", "signature.v1.json must be a JSON object.")

    algo = record.get("algo")
    if algo != "HMAC-SHA256":
        return fail("ALGO_UNSUPPORTED", "Unsupported algo.", details={"algo": algo})

    sig_hex = record.get("signature")
    if not isinstance(sig_hex, str) or not sig_hex:
        return fail("SIGNATURE_INVALID", "Missing or invalid signature field.")

    key = get_signing_key()
    if key is None:
        return fail(
            "SIGNING_KEY_MISSING",
            "SUPPLY_CHAIN_SIGNING_KEY is required in CI for supply-chain verification.",
        )

    try:
        inputs = compute_inputs(root)
    except Exception as e:
        return fail("INPUTS_INVALID", "Failed to compute inputs.", details={"error": str(e)})

    payload = json.dumps(inputs, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    expected_sig = hmac.new(key, payload, sha256).hexdigest()

    if not hmac.compare_digest(expected_sig, sig_hex):
        return fail(
            "SIGNATURE_MISMATCH",
            "Supply-chain signature mismatch.",
            details={"signature_prefix": sig_hex[:12], "expected_prefix": expected_sig[:12]},
        )

    print(
        json.dumps(
            {
                "status": "OK",
                "signature_ok": True,
                "sbom_sha256": inputs.get("sbom", {}).get("sha256"),
                "signature_prefix": sig_hex[:12],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())


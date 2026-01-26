from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from src.ops.commands.common import warn
from src.ops.commands.demo_5min import run_demo_5min


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_zip(path: Path, files: dict[str, bytes]) -> None:
    fixed_dt = (2026, 1, 1, 0, 0, 0)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zi = zipfile.ZipInfo(name, date_time=fixed_dt)
            zf.writestr(zi, data)


def _make_synthetic_vendor_pack(zip_path: Path) -> None:
    tool_name = "semgrep"
    platform = "darwin-arm64"
    tools_dir = "tools/"
    os_part, arch_part = platform.split("-", 1)
    bin_path = f"{tools_dir}{tool_name}/{os_part}/{arch_part}/{tool_name}"

    # Minimal semgrep stub: prints valid JSON when called with --json.
    semgrep_script = (
        b"#!/bin/sh\n"
        b"for a in \"$@\"; do\n"
        b"  if [ \"$a\" = \"--version\" ]; then\n"
        b"    echo \"0.0.0-demo-test\"\n"
        b"    exit 0\n"
        b"  fi\n"
        b"done\n"
        b"echo '{\"results\": [], \"errors\": []}'\n"
        b"exit 0\n"
    )

    contents = [
        {"path": bin_path, "mode": "0o755", "sha256": _sha256_bytes(semgrep_script), "size_bytes": len(semgrep_script)}
    ]

    manifest = {
        "version": "v1",
        "vendor_pack_id": "vendor_pack.semgrep",
        "tool": {"name": tool_name, "version": "0.0.0-demo-test"},
        "platform": platform,
        "created_at_utc": _now_iso_utc(),
        "layout": {
            "manifest_path": "VENDOR_PACK_MANIFEST.json",
            "provenance_path": "PROVENANCE.json",
            "sha256sums_path": "SHA256SUMS.txt",
            "tools_dir": tools_dir,
            "docs_dir": "docs/",
            "extensions_dir": "extensions/",
        },
        "notes": ["synthetic_demo"],
        "contents": contents,
    }

    provenance = {
        "version": "v1",
        "built_at_utc": _now_iso_utc(),
        "build_host": {"os": "darwin", "arch": "arm64"},
        "network_policy": {"download_phase": "OFF", "verify_phase": "OFF"},
        "repo": {"git_sha": "TEST"},
        "upstream": {"name": "semgrep", "version": "0.0.0-demo-test"},
        "outputs": {"zip": zip_path.name},
    }

    manifest_bytes = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    prov_bytes = json.dumps(provenance, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"

    sha_lines = [
        f"{_sha256_bytes(prov_bytes)}  PROVENANCE.json",
        f"{_sha256_bytes(manifest_bytes)}  VENDOR_PACK_MANIFEST.json",
        f"{contents[0]['sha256']}  {bin_path}",
    ]
    sha_text = ("\n".join(sha_lines) + "\n").encode("utf-8")

    files = {
        "PROVENANCE.json": prov_bytes,
        "VENDOR_PACK_MANIFEST.json": manifest_bytes,
        "SHA256SUMS.txt": sha_text,
        bin_path: semgrep_script,
    }
    _write_zip(zip_path, files)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        zip_path = td_path / "vendor_pack.synthetic.demo.zip"
        _make_synthetic_vendor_pack(zip_path)

        outdir = td_path / "demo_out"
        res = run_demo_5min(vendor_pack=zip_path, outdir=outdir, profile="strict", baseline="")
        if res.get("status") != "OK":
            warn(f"FAIL error=DEMO_STATUS expected=OK got={res.get('status')} detail={res.get('error')}")
            return 2

        summary = outdir / "demo_5min.summary.md"
        pointers = outdir / "demo_5min.pointers.v1.json"
        if not summary.exists():
            warn("FAIL error=MISSING_SUMMARY")
            return 2
        if not pointers.exists():
            warn("FAIL error=MISSING_POINTERS")
            return 2

        pobj = json.loads(pointers.read_text(encoding="utf-8"))
        contract_json = str(pobj.get("enforcement_contract_json") or "")
        if not contract_json:
            warn("FAIL error=MISSING_CONTRACT_POINTER")
            return 2
        if not Path(contract_json).exists():
            warn("FAIL error=CONTRACT_JSON_NOT_FOUND")
            return 2

    print(json.dumps({"status": "OK", "checks": ["demo_outputs_exist", "contract_pointer_exists"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())


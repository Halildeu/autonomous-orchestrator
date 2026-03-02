from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from src.ops.commands.common import warn
from src.ops.commands.vendor_pack_verify import run_vendor_pack_verify


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


def _make_synthetic_vendor_pack(zip_path: Path, *, tamper_sha: bool) -> None:
    tool_name = "semgrep"
    platform = "darwin-arm64"
    tools_dir = "tools/"
    os_part, arch_part = platform.split("-", 1)
    bin_path = f"{tools_dir}{tool_name}/{os_part}/{arch_part}/{tool_name}"
    dummy_path = f"{tools_dir}{tool_name}/{os_part}/{arch_part}/site-packages/dummy.txt"

    semgrep_script = (
        b"#!/bin/sh\n"
        b"if [ \"$1\" = \"--version\" ]; then\n"
        b"  echo \"semgrep 0.0.0-test\"\n"
        b"  exit 0\n"
        b"fi\n"
        b"exit 0\n"
    )
    dummy = b"dummy\n"

    contents = [
        {
            "path": bin_path,
            "mode": "0o755",
            "sha256": _sha256_bytes(semgrep_script),
            "size_bytes": len(semgrep_script),
        },
        {
            "path": dummy_path,
            "mode": "0o644",
            "sha256": _sha256_bytes(dummy),
            "size_bytes": len(dummy),
        },
    ]

    manifest = {
        "version": "v1",
        "vendor_pack_id": "vendor_pack.semgrep",
        "tool": {"name": tool_name, "version": "0.0.0-test"},
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
        "notes": ["synthetic"],
        "contents": contents,
    }

    provenance = {
        "version": "v1",
        "built_at_utc": _now_iso_utc(),
        "build_host": {"os": "darwin", "arch": "arm64"},
        "network_policy": {"download_phase": "ON", "verify_phase": "OFF"},
        "repo": {"git_sha": "TEST"},
        "upstream": {"name": "semgrep", "version": "0.0.0-test"},
        "outputs": {"zip": zip_path.name},
    }

    manifest_bytes = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    prov_bytes = json.dumps(provenance, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"

    sha_lines = [
        f"{_sha256_bytes(prov_bytes)}  PROVENANCE.json",
        f"{_sha256_bytes(manifest_bytes)}  VENDOR_PACK_MANIFEST.json",
    ]
    for item in contents:
        sha_lines.append(f"{item['sha256']}  {item['path']}")
    if tamper_sha:
        sha_lines[-1] = f"{'0' * 64}  {dummy_path}"
    sha_text = ("\n".join(sha_lines) + "\n").encode("utf-8")

    files = {
        "PROVENANCE.json": prov_bytes,
        "VENDOR_PACK_MANIFEST.json": manifest_bytes,
        "SHA256SUMS.txt": sha_text,
        bin_path: semgrep_script,
        dummy_path: dummy,
    }
    _write_zip(zip_path, files)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        ok_zip = td_path / "vendor_pack.synthetic.ok.zip"
        bad_zip = td_path / "vendor_pack.synthetic.bad.zip"
        _make_synthetic_vendor_pack(ok_zip, tamper_sha=False)
        _make_synthetic_vendor_pack(bad_zip, tamper_sha=True)

        ok = run_vendor_pack_verify(vendor_pack=ok_zip, outdir=td_path / "out_ok")
        if ok.get("status") != "OK":
            warn(f"FAIL error=EXPECTED_OK got={ok.get('status')} detail={ok.get('error')}")
            return 2

        bad = run_vendor_pack_verify(vendor_pack=bad_zip, outdir=td_path / "out_bad")
        if bad.get("status") != "BLOCKED":
            warn(f"FAIL error=EXPECTED_BLOCKED got={bad.get('status')} detail={bad.get('error')}")
            return 2

    print(json.dumps({"status": "OK", "checks": ["ok_zip_pass", "bad_zip_blocked"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())


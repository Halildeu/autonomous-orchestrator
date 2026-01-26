from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root, warn


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _sha256_stream(stream: Any) -> str:
    h = hashlib.sha256()
    while True:
        chunk = stream.read(1024 * 1024)
        if not chunk:
            break
        h.update(chunk)
    return h.hexdigest()


def _parse_sha256sums(text: str) -> tuple[dict[str, str], list[str]]:
    sha: dict[str, str] = {}
    errors: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            errors.append("INVALID_SHA256SUMS_LINE")
            continue
        digest, path = parts[0].strip().lower(), parts[1].strip()
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            errors.append(f"INVALID_SHA256:{path or 'EMPTY'}")
            continue
        if not path:
            errors.append("EMPTY_PATH")
            continue
        if path in sha:
            errors.append(f"DUPLICATE_PATH:{path}")
            continue
        sha[path] = digest
    return sha, errors


def _is_safe_zip_path(name: str) -> bool:
    if not name or name.startswith("/") or name.startswith("\\"):
        return False
    p = Path(name)
    if p.is_absolute():
        return False
    for part in p.parts:
        if part in {"", ".."}:
            return False
    return True


def _parse_mode(mode_str: Any) -> int | None:
    if not isinstance(mode_str, str):
        return None
    s = mode_str.strip()
    if not s:
        return None
    if s.startswith("0o"):
        s = s[2:]
    try:
        return int(s, 8)
    except Exception:
        return None


def _write_result(outdir: Path, result: dict[str, Any]) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "vendor_pack_verify.result.v1.json").write_text(_dump_json(result), encoding="utf-8")

    lines = [
        "# Vendor Pack Verify (v1)",
        "",
        f"- status: {result.get('status')}",
        f"- reason_code: {result.get('reason_code')}",
        f"- vendor_pack_path: {result.get('vendor_pack_path')}",
        f"- outdir: {result.get('outdir')}",
    ]
    if isinstance(result.get("error"), str) and result.get("error"):
        lines.append(f"- error: {result.get('error')}")
    if isinstance(result.get("vendor_pack"), dict):
        vp = result["vendor_pack"]
        lines.extend(
            [
                f"- vendor_pack_id: {vp.get('vendor_pack_id')}",
                f"- platform: {vp.get('platform')}",
                f"- tool: {vp.get('tool_name')} {vp.get('tool_version')}",
            ]
        )
    if isinstance(result.get("verify"), dict):
        v = result["verify"]
        lines.extend(
            [
                f"- sha256_verified_count: {v.get('sha256_verified_count')}",
                f"- extracted_files_count: {v.get('extracted_files_count')}",
                f"- extract_root: {v.get('extract_root')}",
                f"- tool_bin: {v.get('tool_bin')}",
            ]
        )
    (outdir / "vendor_pack_verify.summary.v1.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_vendor_pack_verify(*, vendor_pack: Path, outdir: Path) -> dict[str, Any]:
    generated_at = _now_iso_utc()
    root = repo_root()

    outdir = (root / outdir).resolve() if not outdir.is_absolute() else outdir.resolve()
    vendor_pack = (root / vendor_pack).resolve() if not vendor_pack.is_absolute() else vendor_pack.resolve()

    result: dict[str, Any] = {
        "version": "v1",
        "status": "BLOCKED",
        "reason_code": "VENDOR_PACK_VERIFY_FAILED",
        "generated_at_utc": generated_at,
        "vendor_pack_path": str(vendor_pack),
        "outdir": str(outdir),
    }

    try:
        if not vendor_pack.exists() or not vendor_pack.is_file():
            result["error"] = "VENDOR_PACK_NOT_FOUND"
            return result

        with zipfile.ZipFile(vendor_pack, "r") as zf:
            names = set(zf.namelist())
            required = {"VENDOR_PACK_MANIFEST.json", "PROVENANCE.json", "SHA256SUMS.txt"}
            missing = sorted(required - names)
            if missing:
                result["error"] = "MISSING_REQUIRED_FILES"
                result["missing_required_files"] = missing
                return result

            try:
                manifest = json.loads(zf.read("VENDOR_PACK_MANIFEST.json").decode("utf-8"))
            except Exception as e:
                result["error"] = "MANIFEST_PARSE_FAIL"
                result["manifest_error"] = str(e)
                return result
            if not isinstance(manifest, dict):
                result["error"] = "MANIFEST_NOT_OBJECT"
                return result

            try:
                provenance = json.loads(zf.read("PROVENANCE.json").decode("utf-8"))
            except Exception as e:
                result["error"] = "PROVENANCE_PARSE_FAIL"
                result["provenance_error"] = str(e)
                return result

            sha_text = zf.read("SHA256SUMS.txt").decode("utf-8")
            sha_map, sha_errors = _parse_sha256sums(sha_text)
            if sha_errors:
                result["error"] = "SHA256SUMS_PARSE_FAIL"
                result["sha256sums_errors"] = sha_errors[:20]
                return result
            if "SHA256SUMS.txt" in sha_map:
                result["error"] = "SHA256SUMS_SELF_REFERENCE"
                return result

            contents = manifest.get("contents") if isinstance(manifest.get("contents"), list) else []
            content_sha: dict[str, str] = {}
            content_mode: dict[str, int] = {}
            content_sizes: dict[str, int] = {}
            for item in contents:
                if not isinstance(item, dict):
                    continue
                p = str(item.get("path") or "").strip()
                if not p:
                    continue
                content_sha[p] = str(item.get("sha256") or "").strip().lower()
                try:
                    content_sizes[p] = int(item.get("size_bytes") or 0)
                except Exception:
                    content_sizes[p] = 0
                mode_int = _parse_mode(item.get("mode"))
                if mode_int is not None:
                    content_mode[p] = mode_int

            expected_sha_count = len(content_sha) + 2
            if len(sha_map) != expected_sha_count:
                result["error"] = "SHA256SUMS_COUNT_MISMATCH"
                result["sha256sums_count"] = len(sha_map)
                result["expected_sha256sums_count"] = expected_sha_count
                return result
            for must in ("PROVENANCE.json", "VENDOR_PACK_MANIFEST.json"):
                if must not in sha_map:
                    result["error"] = "SHA256SUMS_MISSING_META"
                    result["missing_sha256_entries"] = [must]
                    return result

            zip_info_map = {info.filename: info for info in zf.infolist() if info.filename and not info.filename.endswith("/")}
            size_mismatches: list[dict[str, Any]] = []
            for p, expected_size in content_sizes.items():
                if expected_size <= 0:
                    continue
                zi = zip_info_map.get(p)
                if zi is None:
                    size_mismatches.append({"path": p, "error": "MISSING_IN_ZIP"})
                elif int(zi.file_size) != int(expected_size):
                    size_mismatches.append({"path": p, "expected_size": expected_size, "zip_file_size": zi.file_size})
                if len(size_mismatches) >= 20:
                    break
            if size_mismatches:
                result["error"] = "SIZE_MISMATCH"
                result["size_mismatches"] = size_mismatches
                return result

            mismatches: list[dict[str, str]] = []
            for path, expected in sha_map.items():
                if path not in names:
                    mismatches.append({"path": path, "error": "MISSING_IN_ZIP"})
                    if len(mismatches) >= 20:
                        break
                    continue
                with zf.open(path) as f:
                    got = _sha256_stream(f)
                if got != expected:
                    mismatches.append({"path": path, "expected": expected, "got": got})
                    if len(mismatches) >= 20:
                        break
            if mismatches:
                result["error"] = "SHA256_MISMATCH"
                result["sha256_mismatches"] = mismatches
                return result

            manifest_sha_mismatches: list[dict[str, str]] = []
            for p, expected in content_sha.items():
                if not expected:
                    manifest_sha_mismatches.append({"path": p, "error": "EMPTY_SHA256"})
                elif sha_map.get(p) != expected:
                    manifest_sha_mismatches.append(
                        {"path": p, "manifest_sha256": expected, "sha256sums_sha256": sha_map.get(p, "")}
                    )
                if len(manifest_sha_mismatches) >= 20:
                    break
            if manifest_sha_mismatches:
                result["error"] = "MANIFEST_SHA256_MISMATCH"
                result["manifest_sha256_mismatches"] = manifest_sha_mismatches
                return result

            layout = manifest.get("layout") if isinstance(manifest.get("layout"), dict) else {}
            tools_dir = str(layout.get("tools_dir") or "tools/").strip() or "tools/"
            if not tools_dir.endswith("/"):
                tools_dir += "/"

            platform = str(manifest.get("platform") or "").strip() or "unknown-platform"
            tool = manifest.get("tool") if isinstance(manifest.get("tool"), dict) else {}
            tool_name = str(tool.get("name") or "tool").strip() or "tool"
            tool_version = str(tool.get("version") or "unknown").strip() or "unknown"
            vendor_pack_id = str(manifest.get("vendor_pack_id") or "vendor_pack").strip() or "vendor_pack"

            result["vendor_pack"] = {
                "vendor_pack_id": vendor_pack_id,
                "platform": platform,
                "tool_name": tool_name,
                "tool_version": tool_version,
                "sha256sums_count": len(sha_map),
                "contents_count": len(content_sha),
            }
            result["provenance_summary"] = provenance if isinstance(provenance, dict) else {"type": str(type(provenance))}

            safe_ts = generated_at.replace(":", "")
            extract_slug = f"{vendor_pack_id}.{tool_version}.{platform}.{safe_ts}"
            extract_root = outdir / "vendor_pack_extract" / extract_slug
            extract_root.mkdir(parents=True, exist_ok=True)

            extracted_files = 0
            zip_slip_violations: list[str] = []
            for info in zf.infolist():
                name = info.filename
                if not name or name.endswith("/"):
                    continue
                if not name.startswith(tools_dir):
                    continue
                if not _is_safe_zip_path(name):
                    zip_slip_violations.append(name)
                    continue
                dest = extract_root / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, dest.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                mode_int = content_mode.get(name)
                if mode_int is not None:
                    try:
                        os.chmod(dest, mode_int)
                    except Exception:
                        pass
                extracted_files += 1

            if zip_slip_violations:
                result["error"] = "ZIP_SLIP_PATHS"
                result["zip_slip_paths"] = zip_slip_violations[:20]
                return result

            os_part = platform.split("-", 1)[0] if "-" in platform else platform
            arch_part = platform.split("-", 1)[1] if "-" in platform else ""
            if arch_part:
                tool_rel = f"{tools_dir}{tool_name}/{os_part}/{arch_part}/{tool_name}"
            else:
                tool_rel = f"{tools_dir}{tool_name}/{os_part}/{tool_name}"

            tool_bin = extract_root / tool_rel
            if not tool_bin.exists():
                result["error"] = "MISSING_TOOL_BINARY"
                result["missing_tool_path"] = tool_rel
                return result

            site_packages = tool_bin.parent / "site-packages"
            env = dict(os.environ)
            if site_packages.exists():
                prev = env.get("PYTHONPATH", "")
                env["PYTHONPATH"] = str(site_packages) + (os.pathsep + prev if prev else "")

            proc = subprocess.run(
                [str(tool_bin), "--version", "--disable-version-check"],
                cwd=root,
                text=True,
                capture_output=True,
                env=env,
            )
            smoke_out = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
            (outdir / "vendor_pack_verify.semgrep_version.v1.txt").write_text(smoke_out, encoding="utf-8")
            if proc.returncode != 0:
                result["error"] = "SMOKE_FAIL"
                result["smoke_exit_code"] = proc.returncode
                return result

            result["verify"] = {
                "sha256_verified_count": len(sha_map),
                "extracted_files_count": extracted_files,
                "extract_root": str(extract_root),
                "tool_bin": str(tool_bin),
            }
            result["status"] = "OK"
            result["reason_code"] = "OK"
            return result
    except Exception as e:
        result["error"] = "UNEXPECTED_EXCEPTION"
        result["exception"] = str(e)
        return result
    finally:
        _write_result(outdir, result)


def cmd_vendor_pack_verify(args: argparse.Namespace) -> int:
    root = repo_root()

    outdir_arg = str(args.outdir).strip() if args.outdir else ""
    if not outdir_arg:
        warn("FAIL error=OUTDIR_REQUIRED")
        return 2

    vendor_pack_arg = str(args.vendor_pack).strip() if args.vendor_pack else ""
    if not vendor_pack_arg:
        warn("FAIL error=VENDOR_PACK_REQUIRED")
        return 2

    outdir = Path(outdir_arg)
    outdir = (root / outdir).resolve() if not outdir.is_absolute() else outdir.resolve()

    vendor_pack = Path(vendor_pack_arg)
    vendor_pack = (root / vendor_pack).resolve() if not vendor_pack.is_absolute() else vendor_pack.resolve()

    result = run_vendor_pack_verify(vendor_pack=vendor_pack, outdir=outdir)
    print(_dump_json(result), end="")
    return 0 if result.get("status") in {"OK", "WARN"} else 2


def register_vendor_pack_verify_subcommand(parent: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    ap = parent.add_parser(
        "vendor-pack-verify",
        help="Verify a vendor_pack zip (sha256+provenance) and extract tools into a workspace dir (offline).",
    )
    ap.add_argument("--vendor-pack", required=True, help="Path to vendor_pack zip (repo-relative or absolute).")
    ap.add_argument("--outdir", required=True, help="Workspace output dir for evidence + extracted tools.")
    ap.set_defaults(func=cmd_vendor_pack_verify)


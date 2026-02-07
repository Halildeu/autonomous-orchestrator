from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.commands.common import repo_root, warn


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _prepend_env_path(env_var: str, value: str) -> None:
    if not value:
        return
    prev = os.environ.get(env_var, "")
    os.environ[env_var] = value + (os.pathsep + prev if prev else "")


def run_demo_5min(
    *,
    vendor_pack: Path,
    outdir: Path,
    profile: str,
    baseline: str,
) -> dict[str, Any]:
    root = repo_root()
    outdir = (root / outdir).resolve() if not outdir.is_absolute() else outdir.resolve()
    vendor_pack = (root / vendor_pack).resolve() if not vendor_pack.is_absolute() else vendor_pack.resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    started_at = _now_iso_utc()

    demo_summary_md = outdir / "demo_5min.summary.md"
    demo_pointers_json = outdir / "demo_5min.pointers.v1.json"
    demo_result_json = outdir / "demo_5min.result.v1.json"

    docs_product_catalog = root / "docs" / "OPERATIONS" / "product_catalog.v1.json"
    docs_installer_strategy = root / "docs" / "OPERATIONS" / "installer_bundle_strategy.v1.json"

    vendor_verify_outdir = outdir / "vendor_pack_verify"
    enforcement_outdir = outdir / "enforcement_check"

    result: dict[str, Any] = {
        "version": "v1",
        "run_id": "DEMO5-" + started_at.replace(":", "").replace("-", "").replace("T", "").replace("Z", ""),
        "generated_at_utc": started_at,
        "status": "BLOCKED",
        "reason_code": "DEMO_RUN_FAILED",
        "inputs": {
            "vendor_pack": str(vendor_pack),
            "outdir": str(outdir),
            "profile": str(profile),
            "baseline": str(baseline),
        },
        "outputs": {},
        "notes": ["offline_only=true"],
    }

    try:
        if not vendor_pack.exists():
            result["error"] = "VENDOR_PACK_NOT_FOUND"
            return result

        from src.ops.commands.vendor_pack_verify import run_vendor_pack_verify

        vendor_res = run_vendor_pack_verify(vendor_pack=vendor_pack, outdir=vendor_verify_outdir)
        result["vendor_pack_verify"] = vendor_res
        if vendor_res.get("status") != "OK":
            result["error"] = "VENDOR_PACK_VERIFY_FAILED"
            result["reason_code"] = "DEMO_RUN_FAILED"
            return result

        tool_bin = ""
        if isinstance(vendor_res.get("verify"), dict):
            tool_bin = str(vendor_res["verify"].get("tool_bin") or "")
        tool_bin_path = Path(tool_bin) if tool_bin else Path()

        if not tool_bin_path.exists():
            result["error"] = "MISSING_EXTRACTED_TOOL_BIN"
            result["reason_code"] = "DEMO_RUN_FAILED"
            return result

        semgrep_dir = str(tool_bin_path.parent)
        semgrep_site_packages = tool_bin_path.parent / "site-packages"
        _prepend_env_path("PATH", semgrep_dir)
        if semgrep_site_packages.exists():
            _prepend_env_path("PYTHONPATH", str(semgrep_site_packages))

        ruleset = root / "extensions" / "PRJ-ENFORCEMENT-PACK" / "semgrep" / "rules"
        from src.ops.commands.enforcement_check import run_enforcement_check

        enforcement_res = run_enforcement_check(
            outdir=enforcement_outdir,
            ruleset=ruleset,
            profile=str(profile or "strict"),
            baseline=str(baseline or "git:HEAD~1"),
            intake_id="INTAKE-DEMO-5MIN",
            chat=False,
        )
        result["enforcement_check"] = enforcement_res

        pointers = {
            "version": "v1",
            "generated_at_utc": _now_iso_utc(),
            "vendor_pack": str(vendor_pack),
            "vendor_pack_verify_result": str((vendor_verify_outdir / "vendor_pack_verify.result.v1.json")),
            "vendor_pack_verify_summary": str((vendor_verify_outdir / "vendor_pack_verify.summary.v1.md")),
            "enforcement_contract_json": str(enforcement_res.get("contract_json") or ""),
            "enforcement_contract_md": str(enforcement_res.get("contract_md") or ""),
            "enforcement_semgrep_json": str(enforcement_res.get("semgrep_json") or ""),
            "product_catalog_ssot": str(docs_product_catalog),
            "installer_strategy_ssot": str(docs_installer_strategy),
        }
        _write_text(demo_pointers_json, _dump_json(pointers))

        summary_lines = [
            "# RC v0.1 — 5-min Demo (offline)",
            "",
            f"- started_at_utc: {started_at}",
            f"- vendor_pack: {vendor_pack}",
            f"- profile: {profile}",
            f"- baseline: {baseline or 'git:HEAD~1'}",
            "",
            "## Step 1 — vendor-pack-verify",
            f"- status: {vendor_res.get('status')}",
            f"- tool_bin: {tool_bin_path}",
            "",
            "## Step 2 — enforcement-check",
            f"- status: {enforcement_res.get('status')}",
            f"- contract_json: {enforcement_res.get('contract_json')}",
            f"- contract_md: {enforcement_res.get('contract_md')}",
            "",
            "## SSOT pointers",
            f"- product_catalog: {docs_product_catalog}",
            f"- installer_strategy: {docs_installer_strategy}",
            "",
            "## Pointers JSON",
            f"- {demo_pointers_json}",
        ]
        _write_text(demo_summary_md, "\n".join(summary_lines) + "\n")

        result["outputs"] = {
            "demo_summary_md": str(demo_summary_md),
            "demo_pointers_json": str(demo_pointers_json),
            "demo_result_json": str(demo_result_json),
            "vendor_pack_verify_outdir": str(vendor_verify_outdir),
            "enforcement_outdir": str(enforcement_outdir),
        }
        result["status"] = "OK"
        result["reason_code"] = "OK"
        return result
    finally:
        _write_text(demo_result_json, _dump_json(result))


def cmd_demo_5min(args: argparse.Namespace) -> int:
    root = repo_root()

    outdir_arg = str(args.outdir).strip() if args.outdir else ""
    if not outdir_arg:
        warn("FAIL error=OUTDIR_REQUIRED")
        return 2

    vp_arg = str(args.vendor_pack).strip() if args.vendor_pack else ""
    if not vp_arg:
        warn("FAIL error=VENDOR_PACK_REQUIRED")
        return 2

    profile = str(args.profile).strip().lower() if getattr(args, "profile", None) else "strict"
    if profile not in {"default", "strict"}:
        warn("FAIL error=INVALID_PROFILE")
        return 2

    baseline = str(args.baseline).strip() if getattr(args, "baseline", None) else "git:HEAD~1"

    outdir = Path(outdir_arg)
    outdir = (root / outdir).resolve() if not outdir.is_absolute() else outdir.resolve()
    vendor_pack = Path(vp_arg)
    vendor_pack = (root / vendor_pack).resolve() if not vendor_pack.is_absolute() else vendor_pack.resolve()

    result = run_demo_5min(vendor_pack=vendor_pack, outdir=outdir, profile=profile, baseline=baseline)
    print(_dump_json(result), end="")
    return 0 if result.get("status") in {"OK", "WARN"} else 2


def register_demo_5min_subcommand(parent: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    ap = parent.add_parser(
        "demo-5min",
        help="RC v0.1 offline one-command demo: vendor-pack-verify + enforcement-check + pointers.",
    )
    ap.add_argument("--vendor-pack", required=True, help="Path to vendor_pack zip (repo-relative or absolute).")
    ap.add_argument("--outdir", required=True, help="Workspace output dir for demo evidence.")
    ap.add_argument("--profile", default="strict", help="default|strict (default: strict).")
    ap.add_argument("--baseline", default="git:HEAD~1", help="Baseline ref for delta scan (default: git:HEAD~1).")
    ap.set_defaults(func=cmd_demo_5min)


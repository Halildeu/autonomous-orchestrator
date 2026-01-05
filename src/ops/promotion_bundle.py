from __future__ import annotations

import argparse
import fnmatch
import json
import os
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from src.roadmap.sanitize import scan_directory


FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


@dataclass(frozen=True)
class PromotionPolicy:
    enabled: bool
    mode_default: str
    allowlist: list[dict[str, str]]
    denylist: list[str]
    outputs: dict[str, str]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _hash_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _hash_file(path: Path) -> str:
    return _hash_bytes(path.read_bytes())


def _sanitize_scan(incubator_root: Path) -> tuple[bool, list[str]]:
    ok, findings = scan_directory(root=incubator_root)
    if ok:
        return (True, [])
    msgs = [f"{f.path}:{f.rule}" for f in findings]
    return (False, msgs[:20])


def _validate_manifest(manifest: dict[str, Any], core_root: Path) -> list[str]:
    schema_path = core_root / "schemas" / "promotion-manifest.schema.json"
    if not schema_path.exists():
        return ["SCHEMA_MISSING"]
    schema = _load_json(schema_path)
    Draft202012Validator(schema).validate(manifest)
    return []


def _load_policy(core_root: Path, workspace_root: Path) -> PromotionPolicy:
    defaults = PromotionPolicy(
        enabled=False,
        mode_default="customer_clean",
        allowlist=[
            {"from": "incubator/notes/**", "to": "docs/INCUBATOR_NOTES/**"},
            {"from": "incubator/templates/**", "to": "templates/**"},
            {"from": "incubator/patches/**", "to": "patches/**"},
        ],
        denylist=["**/.env", "**/secrets*", "**/*.key", "**/tokens*"],
        outputs={
            "bundle_zip": ".cache/promotion/promotion_bundle.v1.zip",
            "bundle_report": ".cache/promotion/promotion_report.v1.json",
            "core_patch": ".cache/promotion/core_patch.v1.diff",
            "core_patch_md": ".cache/promotion/core_patch_summary.v1.md",
        },
    )

    ws_policy = workspace_root / "policies" / "policy_promotion.v1.json"
    core_policy = core_root / "policies" / "policy_promotion.v1.json"
    policy_path = ws_policy if ws_policy.exists() else core_policy
    if not policy_path.exists():
        return defaults

    try:
        obj = _load_json(policy_path)
    except Exception:
        return defaults
    if not isinstance(obj, dict):
        return defaults

    enabled = bool(obj.get("enabled", defaults.enabled))
    mode_default = obj.get("mode_default", defaults.mode_default)
    if mode_default not in {"customer_clean", "internal_dev"}:
        mode_default = defaults.mode_default

    allowlist = obj.get("allowlist")
    if not isinstance(allowlist, list) or not allowlist:
        allowlist = defaults.allowlist

    denylist = obj.get("denylist")
    if not isinstance(denylist, list):
        denylist = defaults.denylist

    outputs = obj.get("outputs")
    if not isinstance(outputs, dict):
        outputs = defaults.outputs

    return PromotionPolicy(
        enabled=enabled,
        mode_default=str(mode_default),
        allowlist=[
            {"from": str(x.get("from")), "to": str(x.get("to"))}
            for x in allowlist
            if isinstance(x, dict) and isinstance(x.get("from"), str) and isinstance(x.get("to"), str)
        ]
        or defaults.allowlist,
        denylist=[str(x) for x in denylist if isinstance(x, str)] or defaults.denylist,
        outputs={
            "bundle_zip": str(outputs.get("bundle_zip", defaults.outputs["bundle_zip"])),
            "bundle_report": str(outputs.get("bundle_report", defaults.outputs["bundle_report"])),
            "core_patch": str(outputs.get("core_patch", defaults.outputs["core_patch"])),
            "core_patch_md": str(outputs.get("core_patch_md", defaults.outputs["core_patch_md"])),
        },
    )


def _safe_relpath(rel: str) -> str:
    rel = Path(rel).as_posix()
    if rel.startswith("../") or rel.startswith("/") or rel.startswith("..\\"):
        raise ValueError("INVALID_PATH")
    if ".." in Path(rel).parts:
        raise ValueError("INVALID_PATH")
    return rel


def _resolve_workspace_path(workspace_root: Path, rel: str) -> Path:
    rel = _safe_relpath(rel)
    return (workspace_root / rel).resolve()


def _map_dest(rel_path: str, from_pat: str, to_pat: str) -> str:
    rel = Path(rel_path).as_posix()
    from_base = from_pat
    to_base = to_pat
    sub = ""
    if from_pat.endswith("/**"):
        from_base = from_pat[:-3]
        if rel.startswith(from_base):
            sub = rel[len(from_base):].lstrip("/")
    elif from_pat.endswith("*"):
        from_base = from_pat[:-1]
        if rel.startswith(from_base):
            sub = rel[len(from_base):]

    if to_pat.endswith("/**"):
        to_base = to_pat[:-3]
    elif to_pat.endswith("*"):
        to_base = to_pat[:-1]

    dest = to_base
    if sub:
        dest = (Path(to_base) / sub).as_posix()
    dest = _safe_relpath(dest)
    return dest


def _is_binary(data: bytes) -> bool:
    if b"\x00" in data:
        return True
    try:
        data.decode("utf-8")
    except Exception:
        return True
    return False


def _write_zip(out_path: Path, files: list[tuple[str, Path]], report_json: str, readme_text: str) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in [("PROMOTION_REPORT.json", report_json), ("PROMOTION_README.txt", readme_text)]:
            info = zipfile.ZipInfo(name)
            info.date_time = FIXED_ZIP_TIME
            data = content.encode("utf-8")
            zf.writestr(info, data)
            total += len(data)

        for dest, src_path in files:
            data = src_path.read_bytes()
            info = zipfile.ZipInfo(dest)
            info.date_time = FIXED_ZIP_TIME
            zf.writestr(info, data)
            total += len(data)
    return total


def _build_manifest(
    *,
    workspace_root: Path,
    mode: str,
    allowlist: list[dict[str, str]],
    denylist: list[str],
    outputs: dict[str, str],
) -> dict[str, Any]:
    return {
        "version": "v1",
        "generated_at": _now_iso(),
        "workspace_root": str(workspace_root),
        "mode": mode,
        "allowlist": allowlist,
        "denylist": denylist,
        "outputs": outputs,
    }


def run_promotion_bundle(
    *,
    workspace_root: Path,
    core_root: Path,
    mode: str | None,
    dry_run: bool,
) -> dict[str, Any]:
    policy = _load_policy(core_root, workspace_root)
    if not policy.enabled:
        return {"status": "OK", "note": "POLICY_DISABLED"}

    mode_use = mode or policy.mode_default
    if mode_use not in {"customer_clean", "internal_dev"}:
        return {"status": "FAIL", "error_code": "INVALID_MODE"}

    incubator_root = workspace_root / "incubator"
    if not incubator_root.exists():
        return {"status": "FAIL", "error_code": "INCUBATOR_MISSING"}

    ok, findings = _sanitize_scan(incubator_root)
    if not ok:
        return {"status": "FAIL", "error_code": "SANITIZE_VIOLATION", "findings": findings}

    manifest = _build_manifest(
        workspace_root=workspace_root,
        mode=mode_use,
        allowlist=policy.allowlist,
        denylist=policy.denylist,
        outputs=policy.outputs,
    )
    try:
        _validate_manifest(manifest, core_root)
    except Exception as e:
        return {"status": "FAIL", "error_code": "MANIFEST_INVALID", "message": str(e)[:200]}

    all_files: list[str] = []
    for root, dirs, files in os.walk(incubator_root):
        dirs[:] = sorted(dirs)
        for name in sorted(files):
            abs_path = Path(root) / name
            rel = abs_path.resolve().relative_to(workspace_root.resolve()).as_posix()
            all_files.append(rel)

    deny_hits: list[str] = []
    for rel in all_files:
        for pat in policy.denylist:
            if fnmatch.fnmatch(rel, pat):
                deny_hits.append(rel)
                break
    deny_hits = sorted(set(deny_hits))
    if deny_hits:
        return {"status": "FAIL", "error_code": "DENYLIST_HIT", "deny_hits": deny_hits[:20]}

    included: list[dict[str, Any]] = []
    excluded: list[str] = []
    dest_seen: set[str] = set()

    allowlist_sorted = list(policy.allowlist)
    for rel in sorted(all_files):
        matched = False
        for entry in allowlist_sorted:
            from_pat = entry.get("from", "")
            to_pat = entry.get("to", "")
            if not from_pat or not to_pat:
                continue
            if fnmatch.fnmatch(rel, from_pat):
                dest = _map_dest(rel, from_pat, to_pat)
                if dest in dest_seen:
                    return {"status": "FAIL", "error_code": "DEST_CONFLICT", "dest": dest}
                dest_seen.add(dest)
                src_path = (workspace_root / rel).resolve()
                size = src_path.stat().st_size
                included.append(
                    {
                        "src": rel,
                        "dest": dest,
                        "sha256": _hash_file(src_path),
                        "size": size,
                    }
                )
                matched = True
                break
        if not matched:
            excluded.append(rel)

    included_sorted = sorted(included, key=lambda x: str(x.get("dest")))
    excluded_sorted = sorted(set(excluded))

    inputs_seed = "\n".join([f"{i['dest']}:{i['sha256']}" for i in included_sorted])
    bundle_inputs_sha = _hash_bytes(inputs_seed.encode("utf-8"))

    report = {
        "status": "OK",
        "mode": mode_use,
        "included_files": included_sorted,
        "excluded_files": excluded_sorted,
        "deny_hits": deny_hits,
        "hashes": {
            "bundle_inputs_sha256": bundle_inputs_sha,
            "report_sha256": "",
        },
    }

    report_json = _dump_json(report)
    report_sha = _hash_bytes(report_json.encode("utf-8"))
    report["hashes"]["report_sha256"] = report_sha
    report_json = _dump_json(report)

    out_report = _resolve_workspace_path(workspace_root, policy.outputs["bundle_report"])
    out_zip = _resolve_workspace_path(workspace_root, policy.outputs["bundle_zip"])
    out_patch = _resolve_workspace_path(workspace_root, policy.outputs["core_patch"])
    out_patch_md = _resolve_workspace_path(workspace_root, policy.outputs["core_patch_md"])

    if dry_run:
        return {
            "status": "WOULD_WRITE",
            "included": len(included_sorted),
            "out": str(out_zip),
        }

    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text(report_json, encoding="utf-8")

    files_for_zip = []
    for item in included_sorted:
        src = (workspace_root / item["src"]).resolve()
        files_for_zip.append((item["dest"], src))

    readme = (
        "Promotion bundle (draft-only).\n"
        "Use the core_patch.v1.diff as a manual reference; no auto-apply.\n"
        "Verify integrity before applying.\n"
    )
    bundle_bytes = _write_zip(out_zip, files_for_zip, report_json, readme)

    # Build core patch diff (text-only).
    diff_lines: list[str] = []
    added: list[str] = []
    modified: list[str] = []
    skipped_binary: list[str] = []

    for item in included_sorted:
        dest = item["dest"]
        src_path = (workspace_root / item["src"]).resolve()
        data = src_path.read_bytes()
        if _is_binary(data):
            skipped_binary.append(dest)
            continue
        src_text = data.decode("utf-8")

        core_path = (core_root / dest).resolve()
        if core_path.exists():
            try:
                core_data = core_path.read_bytes()
            except Exception:
                skipped_binary.append(dest)
                continue
            if _is_binary(core_data):
                skipped_binary.append(dest)
                continue
            core_text = core_data.decode("utf-8")
            if core_text == src_text:
                continue
            modified.append(dest)
            from_lines = core_text.splitlines(keepends=True)
            to_lines = src_text.splitlines(keepends=True)
            diff_lines.extend(
                list(
                    __import__("difflib").unified_diff(
                        from_lines,
                        to_lines,
                        fromfile=f"a/{dest}",
                        tofile=f"b/{dest}",
                    )
                )
            )
        else:
            added.append(dest)
            to_lines = src_text.splitlines(keepends=True)
            diff_lines.extend(
                list(
                    __import__("difflib").unified_diff(
                        [],
                        to_lines,
                        fromfile="/dev/null",
                        tofile=f"b/{dest}",
                    )
                )
            )

    out_patch.parent.mkdir(parents=True, exist_ok=True)
    out_patch.write_text("".join(diff_lines), encoding="utf-8")

    bundle_sha = _hash_file(out_zip)
    report_sha_final = _hash_file(out_report)
    summary_lines = [
        "# Promotion bundle core patch summary",
        "",
        "Draft only. No auto-apply.",
        "",
        f"Bundle zip: {out_zip.as_posix()}",
        f"Bundle sha256: {bundle_sha}",
        f"Report sha256: {report_sha_final}",
        "",
        f"Added files: {len(added)}",
        f"Modified files: {len(modified)}",
        f"Skipped binary files: {len(skipped_binary)}",
        "",
    ]
    if added:
        summary_lines.append("## Added")
        for p in added:
            summary_lines.append(f"- {p}")
        summary_lines.append("")
    if modified:
        summary_lines.append("## Modified")
        for p in modified:
            summary_lines.append(f"- {p}")
        summary_lines.append("")
    if skipped_binary:
        summary_lines.append("## Skipped (binary)")
        for p in skipped_binary:
            summary_lines.append(f"- {p}")
        summary_lines.append("")

    out_patch_md.parent.mkdir(parents=True, exist_ok=True)
    out_patch_md.write_text("\n".join(summary_lines).rstrip() + "\n", encoding="utf-8")

    return {
        "status": "OK",
        "mode": mode_use,
        "included": len(included_sorted),
        "out_zip": str(out_zip),
        "out_report": str(out_report),
        "out_patch": str(out_patch),
        "out_patch_md": str(out_patch_md),
        "bundle_bytes": bundle_bytes,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.ops.promotion_bundle", add_help=True)
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--mode", default="")
    ap.add_argument("--dry-run", default="true")
    args = ap.parse_args(argv)

    core_root = _repo_root()
    ws_root = Path(str(args.workspace_root)).resolve()
    if not ws_root.exists() or not ws_root.is_dir():
        print(json.dumps({"status": "FAIL", "error_code": "WORKSPACE_ROOT_INVALID"}, ensure_ascii=False, sort_keys=True))
        return 2

    dry_run = str(args.dry_run).strip().lower() in {"1", "true", "yes", "y", "on"}
    mode = str(args.mode).strip() or None

    res = run_promotion_bundle(workspace_root=ws_root, core_root=core_root, mode=mode, dry_run=dry_run)
    print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    return 0 if res.get("status") in {"OK", "WARN", "WOULD_WRITE"} else 2


if __name__ == "__main__":
    raise SystemExit(main())

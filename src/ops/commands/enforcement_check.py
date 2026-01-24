from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from src.ops.commands.common import repo_root, warn


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return (None, str(e))
    return (obj if isinstance(obj, dict) else None, None)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _resolve_profile_name(profile: str) -> str:
    p = str(profile or "").strip().lower()
    if p == "strict":
        return "strict_profile"
    return "default_profile"


def _resolve_git_baseline_ref(baseline: str) -> str:
    raw = str(baseline or "").strip()
    if raw.startswith("git:"):
        return raw[len("git:") :].strip() or "HEAD~1"
    return raw or "HEAD~1"


def _git_diff_paths(root: Path, baseline_ref: str) -> tuple[list[str], str | None]:
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", f"{baseline_ref}..HEAD"],
            cwd=root,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        return ([], "GIT_NOT_FOUND")
    if proc.returncode != 0:
        return ([], "DELTA_COMPUTE_FAILED")
    paths = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    return (paths, None)


def _derive_ep_id(engine_rule_id: str, metadata: dict[str, Any]) -> str:
    for key in ("ep_id", "epId", "ep", "EP"):
        v = metadata.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()

    s = str(engine_rule_id or "")
    m = re.search(r"\\bep0*([0-9]{1,3})\\b", s, flags=re.IGNORECASE)
    if not m:
        return "UNKNOWN_RULE"
    num = m.group(1)
    try:
        n = int(num)
    except Exception:
        return "UNKNOWN_RULE"
    return f"EP-{n:03d}"


def _map_semgrep_severity(raw: Any) -> str:
    s = str(raw or "").strip().upper()
    if s in {"INFO", "HINT"}:
        return "LOW"
    if s in {"WARNING", "WARN"}:
        return "MEDIUM"
    if s in {"ERROR", "CRITICAL"}:
        return "HIGH"
    return "MEDIUM"


def _load_severity_matrix(root: Path, matrix_path: Path, profile_name: str) -> tuple[dict[str, Any] | None, str | None]:
    matrix_obj, err = _load_json(matrix_path)
    if err:
        return (None, err)

    profiles = matrix_obj.get("profiles") if isinstance(matrix_obj, dict) else None
    if not isinstance(profiles, dict) or profile_name not in profiles:
        return (None, "INVALID_PROFILE")

    defaults = matrix_obj.get("defaults") if isinstance(matrix_obj.get("defaults"), dict) else {}
    return (
        {
            "profile_name": profile_name,
            "profile": profiles.get(profile_name, {}),
            "defaults": defaults,
        },
        None,
    )


def _gate_action_for_rule(matrix: dict[str, Any], rule_id: str) -> str:
    prof = matrix.get("profile") if isinstance(matrix.get("profile"), dict) else {}
    if isinstance(prof.get(rule_id), str) and prof.get(rule_id):
        return str(prof.get(rule_id))
    defaults = matrix.get("defaults") if isinstance(matrix.get("defaults"), dict) else {}
    if isinstance(defaults.get("unknown_rule"), str) and defaults.get("unknown_rule"):
        return str(defaults.get("unknown_rule"))
    return "WARN"


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run_semgrep(
    *,
    root: Path,
    ruleset: Path,
    targets: list[str],
    out_json_path: Path,
    out_stdout_path: Path,
) -> tuple[dict[str, Any], list[str]]:
    reasons: list[str] = []
    semgrep_bin = shutil.which("semgrep")
    if not semgrep_bin:
        reasons.append("ENGINE_MISSING_SEMGREP")
        payload = {"results": [], "errors": [{"type": "ENGINE_MISSING", "message": "semgrep not found"}]}
        _write_text(out_json_path, _dump_json(payload))
        _write_text(out_stdout_path, "ENGINE_MISSING_SEMGREP\n")
        return payload, reasons

    cmd = [
        semgrep_bin,
        "--config",
        str(ruleset),
        "--metrics=off",
        "--disable-version-check",
        "--json",
    ]
    if targets:
        cmd.extend(targets)
    else:
        cmd.append(".")

    proc = subprocess.run(cmd, cwd=root, text=True, capture_output=True)
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    _write_text(out_stdout_path, stdout + ("\n" if stdout and not stdout.endswith("\n") else "") + stderr)

    if proc.returncode != 0:
        reasons.append("ENGINE_EXEC_FAILED")

    try:
        payload = json.loads(stdout) if stdout.strip() else {"results": [], "errors": []}
        if not isinstance(payload, dict):
            payload = {"results": [], "errors": [{"type": "PARSE_FAIL", "message": "non-dict json"}]}
    except Exception:
        payload = {"results": [], "errors": [{"type": "PARSE_FAIL", "message": "invalid json"}]}
        reasons.append("ENGINE_EXEC_FAILED")

    _write_text(out_json_path, _dump_json(payload))
    return payload, reasons


def _contract_schema_validator(schema_path: Path) -> Draft202012Validator:
    schema_obj, err = _load_json(schema_path)
    if err or not schema_obj:
        raise ValueError("CONTRACT_SCHEMA_LOAD_FAILED")
    Draft202012Validator.check_schema(schema_obj)
    return Draft202012Validator(schema_obj)


def _build_contract_report(
    *,
    root: Path,
    intake_id: str,
    rule_set_version: str,
    profile_name: str,
    matrix: dict[str, Any],
    semgrep_payload: dict[str, Any],
    semgrep_raw_rel: str,
    delta_paths: list[str],
    delta_paths_rel: str | None,
    baseline_ref: str | None,
    evidence_paths: list[str],
    reasons: list[str],
) -> dict[str, Any]:
    delta_set = set(delta_paths)
    results = semgrep_payload.get("results") if isinstance(semgrep_payload, dict) else None
    results_list = results if isinstance(results, list) else []

    violations: list[dict[str, Any]] = []
    out_of_scope = 0
    blocked = 0

    for i, r in enumerate(results_list, start=1):
        if not isinstance(r, dict):
            continue
        extra = r.get("extra") if isinstance(r.get("extra"), dict) else {}
        metadata = extra.get("metadata") if isinstance(extra.get("metadata"), dict) else {}
        engine_rule_id = str(r.get("check_id") or "")
        rule_id = _derive_ep_id(engine_rule_id, metadata)
        file_path = str(r.get("path") or "")

        start = r.get("start") if isinstance(r.get("start"), dict) else {}
        end = r.get("end") if isinstance(r.get("end"), dict) else {}
        start_line = int(start.get("line") or 1)
        end_line = int(end.get("line") or start_line)

        message = str(extra.get("message") or "").strip() or str(r.get("check_id") or "violation").strip()
        severity = _map_semgrep_severity(extra.get("severity"))

        classification = "DELTA"
        if delta_paths:
            if file_path not in delta_set:
                classification = "OUT_OF_SCOPE"
                out_of_scope += 1

        gate_action = _gate_action_for_rule(matrix, rule_id)
        if gate_action == "BLOCKED":
            blocked += 1

        fp_input = f"{rule_id}|{engine_rule_id}|{file_path}|{start_line}|{end_line}"
        fingerprint = _sha256_text(fp_input)[:16]
        violation_id = f"V-{i:04d}"

        violations.append(
            {
                "violation_id": violation_id,
                "rule_id": rule_id,
                "engine": "semgrep",
                "engine_rule_id": engine_rule_id,
                "classification": classification,
                "severity": severity,
                "message": message,
                "file_path": file_path or "UNKNOWN_PATH",
                "start_line": max(1, start_line),
                "end_line": max(1, end_line),
                "fingerprint": fingerprint,
                "help": str(metadata.get("rationale") or metadata.get("help") or ""),
                "references": [rule_id],
                "evidence_paths": [p for p in [semgrep_raw_rel, delta_paths_rel] if isinstance(p, str) and p],
            }
        )

    delta_dirty = sum(1 for v in violations if v.get("classification") == "DELTA")

    status = "OK"
    if out_of_scope > 0:
        status = "FAIL"
        if "OUT_OF_SCOPE_VIOLATIONS_GT0" not in reasons:
            reasons.append("OUT_OF_SCOPE_VIOLATIONS_GT0")
    elif blocked > 0:
        status = "BLOCKED"
    elif violations:
        status = "WARN"
    elif reasons:
        # Missing engine, missing files, etc.
        status = "BLOCKED"

    baseline_source: dict[str, Any] = {"kind": "unknown"}
    if baseline_ref:
        baseline_source = {"kind": "git_commit", "ref": f"git:{baseline_ref}"}

    delta_source: dict[str, Any] = {"kind": "unknown"}
    if baseline_ref:
        delta_source = {"kind": "git_diff", "ref": f"git:{baseline_ref}..HEAD"}
    if delta_paths:
        delta_source["paths"] = sorted(delta_set)

    bundle_id = "BUNDLE-" + _sha256_text("|".join(sorted(evidence_paths) + [profile_name, rule_set_version]))[:10]
    report = {
        "version": "v1",
        "generated_at": _now_iso_utc(),
        "intake_id": intake_id,
        "run_id": "ENFCHK-" + _sha256_text(_now_iso_utc())[:10],
        "status": status,
        "rule_set_version": rule_set_version,
        "stats": {
            "baseline": {"dirty_count": 0, "source": baseline_source},
            "delta": {
                "dirty_count": int(delta_dirty),
                "changed_files_count": int(len(delta_paths)),
                "source": delta_source,
            },
            "out_of_scope": {"violations_count": int(out_of_scope), "notes": []},
            "totals": {"violations_count": int(len(violations))},
        },
        "violations": violations,
        "evidence_bundle": {
            "bundle_id": bundle_id,
            "evidence_paths": sorted(set([p for p in evidence_paths if isinstance(p, str) and p])),
            "delta_input_paths": [delta_paths_rel] if isinstance(delta_paths_rel, str) and delta_paths_rel else [],
            "raw_tool_outputs": [semgrep_raw_rel] if semgrep_raw_rel else [],
            "notes": [f"profile={profile_name}", f"baseline={baseline_ref or ''}"],
        },
        "reasons": sorted(set([r for r in reasons if isinstance(r, str) and r])),
        "notes": [],
    }
    return report


def run_enforcement_check(
    *,
    outdir: Path,
    ruleset: Path,
    profile: str,
    baseline: str,
    intake_id: str,
    chat: bool,
) -> dict[str, Any]:
    root = repo_root()
    outdir.mkdir(parents=True, exist_ok=True)

    intake_id_norm = (str(intake_id).strip() if intake_id else "") or "UNKNOWN"
    profile_name = _resolve_profile_name(profile)

    extension_root = root / "extensions" / "PRJ-ENFORCEMENT-PACK"
    manifest_path = extension_root / "extension.manifest.v1.json"
    schema_path = extension_root / "contract" / "enforcement-check.schema.v1.json"
    matrix_path = extension_root / "contract" / "severity_matrix.v1.json"

    reasons: list[str] = []
    evidence_paths: list[str] = [
        str(schema_path.relative_to(root).as_posix()) if schema_path.exists() else "",
        str(matrix_path.relative_to(root).as_posix()) if matrix_path.exists() else "",
        str(ruleset.relative_to(root).as_posix()) if ruleset.exists() else "",
    ]
    evidence_paths = [p for p in evidence_paths if p]

    if not schema_path.exists():
        reasons.append("MISSING_CONTRACT_SCHEMA")
    if not matrix_path.exists():
        reasons.append("MISSING_SEVERITY_MATRIX")
    if not ruleset.exists():
        reasons.append("MISSING_RULESET_PATH")

    semver = "0.0.0"
    if manifest_path.exists():
        mobj, _ = _load_json(manifest_path)
        if isinstance(mobj, dict) and isinstance(mobj.get("semver"), str) and mobj.get("semver"):
            semver = str(mobj.get("semver"))
    rule_set_version = f"PRJ-ENFORCEMENT-PACK.semgrep_oss@{semver}"

    delta_paths: list[str] = []
    delta_paths_rel: str | None = None
    baseline_ref: str | None = None
    if baseline.strip():
        baseline_ref = _resolve_git_baseline_ref(baseline)
        delta_paths, err = _git_diff_paths(root, baseline_ref)
        if err:
            reasons.append(err)

    # Output paths (always under outdir)
    run_tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    semgrep_json_path = outdir / f"semgrep_findings.{run_tag}.json"
    semgrep_stdout_path = outdir / f"semgrep_stdout.{run_tag}.txt"
    delta_paths_path = outdir / f"delta_paths.{run_tag}.txt"
    contract_json_path = outdir / f"enforcement_check.{run_tag}.v1.json"
    contract_md_path = outdir / f"enforcement_check.{run_tag}.v1.md"

    if delta_paths:
        _write_text(delta_paths_path, "\n".join(sorted(set(delta_paths))) + "\n")
        try:
            delta_paths_rel = delta_paths_path.relative_to(root).as_posix()
        except Exception:
            delta_paths_rel = str(delta_paths_path)

    try:
        semgrep_raw_rel = semgrep_json_path.relative_to(root).as_posix()
    except Exception:
        semgrep_raw_rel = str(semgrep_json_path)

    if reasons and any(r.startswith("MISSING_") for r in reasons):
        semgrep_payload = {"results": [], "errors": [{"type": "PRECONDITION_FAIL", "message": "missing inputs"}]}
        _write_text(semgrep_json_path, _dump_json(semgrep_payload))
        _write_text(semgrep_stdout_path, "PRECONDITION_FAIL\n")
    else:
        semgrep_payload, semgrep_reasons = _run_semgrep(
            root=root,
            ruleset=ruleset,
            targets=sorted(set(delta_paths)) if delta_paths else [],
            out_json_path=semgrep_json_path,
            out_stdout_path=semgrep_stdout_path,
        )
        reasons.extend(semgrep_reasons)

    matrix, err = _load_severity_matrix(root, matrix_path, profile_name)
    if err:
        reasons.append(err)
        matrix = {
            "profile_name": profile_name,
            "profile": {},
            "defaults": {"unknown_rule": "WARN", "advisory_mode": False},
        }

    extra_evidence_paths: list[str] = []
    for p in (contract_json_path, contract_md_path):
        try:
            extra_evidence_paths.append(p.relative_to(root).as_posix())
        except Exception:
            extra_evidence_paths.append(str(p))

    report = _build_contract_report(
        root=root,
        intake_id=intake_id_norm,
        rule_set_version=rule_set_version,
        profile_name=profile_name,
        matrix=matrix,
        semgrep_payload=semgrep_payload,
        semgrep_raw_rel=semgrep_raw_rel,
        delta_paths=delta_paths,
        delta_paths_rel=delta_paths_rel,
        baseline_ref=baseline_ref,
        evidence_paths=evidence_paths + extra_evidence_paths,
        reasons=list(reasons),
    )

    try:
        validator = _contract_schema_validator(schema_path)
        errors = [e.message for e in validator.iter_errors(report)]
        if errors:
            report["status"] = "FAIL"
            report["reasons"] = sorted(set(report.get("reasons", []) + ["CONTRACT_SCHEMA_INVALID"]))
            report["notes"] = list(report.get("notes", [])) + [f"schema_errors_count={len(errors)}"]
    except Exception:
        report["status"] = "FAIL"
        report["reasons"] = sorted(set(report.get("reasons", []) + ["CONTRACT_SCHEMA_VALIDATE_FAILED"]))

    _write_text(contract_json_path, _dump_json(report))

    summary_lines = [
        "# Enforcement Check (v1 contract)",
        "",
        f"status={report.get('status')}",
        f"profile={profile_name}",
        f"rule_set_version={rule_set_version}",
        f"violations_total={report.get('stats', {}).get('totals', {}).get('violations_count')}",
        f"delta_dirty={report.get('stats', {}).get('delta', {}).get('dirty_count')}",
        f"out_of_scope={report.get('stats', {}).get('out_of_scope', {}).get('violations_count')}",
        "",
        "Evidence:",
        f"- contract_json={contract_json_path}",
        f"- contract_md={contract_md_path}",
        f"- semgrep_json={semgrep_json_path}",
    ]
    if delta_paths_rel:
        summary_lines.append(f"- delta_paths={delta_paths_path}")
    if report.get("reasons"):
        summary_lines.append("")
        summary_lines.append("Reasons:")
        for r in report.get("reasons", []):
            summary_lines.append(f"- {r}")

    _write_text(contract_md_path, "\n".join(summary_lines) + "\n")

    if chat:
        print("PREVIEW:")
        print("PROGRAM-LED: enforcement-check (offline-first)")
        print(f"profile={profile_name} baseline={baseline_ref or ''}")
        print("RESULT:")
        print(f"status={report.get('status')}")
        print("EVIDENCE:")
        try:
            print(str(contract_json_path.relative_to(root)))
        except Exception:
            print(str(contract_json_path))
        print("ACTIONS:")
        print("enforcement-check")
        print("NEXT:")
        print("Devam et / Durumu göster / Duraklat")

    return {
        "status": str(report.get("status") or "UNKNOWN"),
        "profile": profile_name,
        "outdir": str(outdir),
        "contract_json": str(contract_json_path),
        "contract_md": str(contract_md_path),
        "semgrep_json": str(semgrep_json_path),
        "semgrep_stdout": str(semgrep_stdout_path),
    }

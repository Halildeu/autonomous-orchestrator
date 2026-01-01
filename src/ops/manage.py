from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import time

from jsonschema import Draft202012Validator

from src.evidence.integrity_verify import MANIFEST_NAME, verify_run_dir
from src.ops.reaper import compute_reaper_report, parse_bool as parse_reaper_bool, parse_iso8601 as parse_reaper_iso, write_report as write_reaper_report


def repo_root() -> Path:
    # src/ops/manage.py -> ops -> src -> repo root
    return Path(__file__).resolve().parents[2]


def warn(msg: str) -> None:
    print(msg, file=sys.stderr)


def load_json_file(path: Path) -> tuple[Any | None, str | None]:
    try:
        return (json.loads(path.read_text(encoding="utf-8")), None)
    except Exception as e:
        return (None, str(e))


def parse_iso8601_ts(value: Any) -> float:
    if not isinstance(value, str) or not value:
        return 0.0
    try:
        return datetime.fromisoformat(value).timestamp()
    except Exception:
        return 0.0


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    if not rows:
        print(" | ".join(headers))
        print("count=0")
        return

    widths = [len(h) for h in headers]
    for r in rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], len(cell))

    def fmt(r: list[str]) -> str:
        return " | ".join((r[i] if i < len(r) else "").ljust(widths[i]) for i in range(len(headers)))

    print(fmt(headers))
    print("-+-".join("-" * w for w in widths))
    for r in rows:
        print(fmt(r))
    print(f"count={len(rows)}")


def is_git_work_tree(root: Path) -> bool:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=root,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        return False
    return proc.returncode == 0 and (proc.stdout or "").strip() == "true"


def git_ref_exists(root: Path, ref: str) -> bool:
    if not ref or not isinstance(ref, str):
        return False
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
            cwd=root,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        return False
    return proc.returncode == 0


def run_step(root: Path, cmd: list[str], *, stage: str, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        cwd=root,
        text=True,
        capture_output=True,
        env=env,
    )
    if proc.returncode != 0:
        # Keep outputs minimal/safe; do not print secrets.
        print(f"POLICY_CHECK_FAIL stage={stage}")
        return (proc.returncode, proc.stdout or "", proc.stderr or "")
    return (0, proc.stdout or "", proc.stderr or "")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def schema_path_for_policy_name(root: Path, policy_filename: str) -> Path:
    name = Path(policy_filename).name
    base = name.split(".v", 1)[0] if ".v" in name else name.rsplit(".json", 1)[0]
    schema_name = base.replace("_", "-") + ".schema.json"
    return root / "schemas" / schema_name


def load_validator(schema_path: Path) -> Draft202012Validator:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def policy_paths_from_obj(obj: Any, prefix: str = "") -> dict[str, Any]:
    # Flatten leaf values to dot paths (dict recursion only; lists treated as leaves).
    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        for k in sorted(obj.keys()):
            if not isinstance(k, str):
                continue
            path = f"{prefix}.{k}" if prefix else k
            v = obj.get(k)
            if isinstance(v, dict):
                out.update(policy_paths_from_obj(v, prefix=path))
            else:
                out[path] = v
    else:
        out[prefix or "$"] = obj
    return out


def cmd_policy_export(args: argparse.Namespace) -> int:
    root = repo_root()
    name = Path(str(args.name)).name
    policy_path = root / "policies" / name
    if not policy_path.exists():
        warn(f"ERROR: policy not found: {name}")
        return 2

    content = policy_path.read_text(encoding="utf-8")
    if args.out:
        out_path = Path(str(args.out))
        out_path = (root / out_path).resolve() if not out_path.is_absolute() else out_path.resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")

    print(content.rstrip("\n"))
    return 0


def cmd_policy_validate(args: argparse.Namespace) -> int:
    root = repo_root()
    file_path = Path(str(args.file))
    file_path = (root / file_path).resolve() if not file_path.is_absolute() else file_path.resolve()
    if not file_path.exists():
        warn(f"FAIL file={file_path} error=FILE_NOT_FOUND")
        return 2

    try:
        infer_schema = parse_reaper_bool(str(args.infer_schema))
    except ValueError:
        warn(f"FAIL file={file_path} error=INVALID_ARGS")
        return 2

    try:
        instance = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        warn(f"FAIL file={file_path} error=JSON_INVALID")
        return 2

    # Strict mapping by policy filename (default): policy_security.v1.json -> schemas/policy-security.schema.json.
    mapped_schema = schema_path_for_policy_name(root, file_path.name)
    schema_to_use: Path | None = mapped_schema if mapped_schema.exists() else None
    inferred = False

    if schema_to_use is None:
        if not infer_schema:
            warn(f"FAIL file={file_path} schema={mapped_schema.name} error=SCHEMA_NOT_FOUND")
            return 2

        # Best-effort inference (opt-in): try to infer by validating against all known policy schemas.
        schema_candidates = sorted((root / "schemas").glob("policy-*.schema.json"), key=lambda p: p.name)
        best_schema: Path | None = None
        best_errors: list[str] = []
        best_count: int | None = None
        matches: list[Path] = []

        for sp in schema_candidates:
            try:
                validator = load_validator(sp)
            except Exception:
                continue
            errors = sorted(validator.iter_errors(instance), key=lambda e: e.json_path)
            if not errors:
                matches.append(sp)
                continue
            msgs = []
            for err in errors[:3]:
                where = err.json_path or "$"
                msgs.append(f"{where}: {err.message}")
            if best_count is None or len(errors) < best_count:
                best_count = len(errors)
                best_schema = sp
                best_errors = msgs

        if len(matches) == 1:
            schema_to_use = matches[0]
            inferred = True
            warn(f"SCHEMA_INFERRED schema={schema_to_use.name}")
        elif len(matches) > 1:
            warn(
                "FAIL file="
                + str(file_path)
                + " error=AMBIGUOUS_SCHEMA matches="
                + ",".join(p.name for p in matches)
            )
            return 2
        else:
            schema_name = best_schema.name if best_schema else mapped_schema.name
            detail = best_errors[0] if best_errors else "no_matching_schema"
            warn(f"FAIL file={file_path} schema={schema_name} error={detail}")
            return 2

    try:
        validator = load_validator(schema_to_use)
    except Exception as e:
        warn(f"FAIL file={file_path} schema={schema_to_use.name} error=SCHEMA_INVALID")
        return 2

    errors = sorted(validator.iter_errors(instance), key=lambda e: e.json_path)
    if errors:
        err = errors[0]
        where = err.json_path or "$"
        warn(f"FAIL file={file_path} schema={schema_to_use.name} error={where}: {err.message}")
        return 2

    print(f"OK file={file_path} schema={schema_to_use.name}")
    return 0


def cmd_policy_diff(args: argparse.Namespace) -> int:
    root = repo_root()
    path_a = Path(str(args.a))
    path_b = Path(str(args.b))
    path_a = (root / path_a).resolve() if not path_a.is_absolute() else path_a.resolve()
    path_b = (root / path_b).resolve() if not path_b.is_absolute() else path_b.resolve()

    try:
        a_obj = json.loads(path_a.read_text(encoding="utf-8"))
        b_obj = json.loads(path_b.read_text(encoding="utf-8"))
    except Exception:
        warn("FAIL error=JSON_INVALID")
        return 2

    a_flat = policy_paths_from_obj(a_obj)
    b_flat = policy_paths_from_obj(b_obj)

    a_keys = set(a_flat.keys())
    b_keys = set(b_flat.keys())

    added = sorted(b_keys - a_keys)
    removed = sorted(a_keys - b_keys)
    changed_values = sorted([k for k in sorted(a_keys & b_keys) if a_flat.get(k) != b_flat.get(k)])
    changed = sorted(set(added) | set(removed) | set(changed_values))

    payload = {"changed_keys": changed, "added_keys": added, "removed_keys": removed}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_policy_apply(args: argparse.Namespace) -> int:
    root = repo_root()
    file_path = Path(str(args.file))
    file_path = (root / file_path).resolve() if not file_path.is_absolute() else file_path.resolve()
    if not file_path.exists():
        warn("FAIL error=FILE_NOT_FOUND")
        return 2

    try:
        dry_run = parse_reaper_bool(str(args.dry_run))
    except ValueError as e:
        warn("FAIL error=INVALID_ARGS")
        return 2

    try:
        infer_schema = parse_reaper_bool(str(args.infer_schema))
    except ValueError:
        warn("FAIL error=INVALID_ARGS")
        return 2

    basename = file_path.name
    if not (basename.startswith("policy_") and ".v" in basename and basename.endswith(".json")):
        warn("FAIL error=INVALID_POLICY_FILENAME")
        return 2

    policies_dir = (root / "policies").resolve()
    dest_path = (policies_dir / basename).resolve()
    try:
        dest_path.relative_to(policies_dir)
    except Exception:
        warn("FAIL error=PATH_TRAVERSAL")
        return 2

    if not dest_path.exists():
        warn("FAIL error=TARGET_NOT_FOUND")
        return 2

    try:
        instance = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        warn("FAIL error=JSON_INVALID")
        return 2

    # Validate candidate file (against schema derived from target policy name).
    schema_path = schema_path_for_policy_name(root, basename)
    schema_to_use: Path | None = schema_path if schema_path.exists() else None

    if schema_to_use is None:
        if not infer_schema:
            warn("FAIL error=SCHEMA_NOT_FOUND")
            return 2

        schema_candidates = sorted((root / "schemas").glob("policy-*.schema.json"), key=lambda p: p.name)
        matches: list[Path] = []
        best_schema: Path | None = None
        best_errors: list[str] = []
        best_count: int | None = None

        for sp in schema_candidates:
            try:
                validator = load_validator(sp)
            except Exception:
                continue
            errors = sorted(validator.iter_errors(instance), key=lambda e: e.json_path)
            if not errors:
                matches.append(sp)
                continue
            msgs = []
            for err in errors[:3]:
                where = err.json_path or "$"
                msgs.append(f"{where}: {err.message}")
            if best_count is None or len(errors) < best_count:
                best_count = len(errors)
                best_schema = sp
                best_errors = msgs

        if len(matches) == 1:
            schema_to_use = matches[0]
            warn(f"SCHEMA_INFERRED schema={schema_to_use.name}")
        elif len(matches) > 1:
            warn("FAIL error=AMBIGUOUS_SCHEMA")
            return 2
        else:
            schema_name = best_schema.name if best_schema else schema_path.name
            detail = best_errors[0] if best_errors else "no_matching_schema"
            warn(f"FAIL error={detail} schema={schema_name}")
            return 2

    try:
        validator = load_validator(schema_to_use)
    except Exception:
        warn("FAIL error=SCHEMA_INVALID")
        return 2

    errors = sorted(validator.iter_errors(instance), key=lambda e: e.json_path)
    if errors:
        err = errors[0]
        where = err.json_path or "$"
        warn(f"FAIL error=SCHEMA_MISMATCH where={where}")
        return 2

    # Dry-run: validate only + run policy-check on current tree.
    if dry_run:
        proc = subprocess.run(
            [sys.executable, "-m", "src.ops.manage", "policy-check", "--source", "fixtures"],
            cwd=root,
            text=True,
            capture_output=True,
        )
        if proc.returncode != 0:
            warn("FAIL error=POLICY_CHECK_FAILED")
            return 2
        print("OK dry_run=true")
        return 0

    # Apply safely: backup existing, overwrite, policy-check; rollback on failure.
    backup = dest_path.read_bytes()
    try:
        dest_path.write_bytes(file_path.read_bytes())
        proc = subprocess.run(
            [sys.executable, "-m", "src.ops.manage", "policy-check", "--source", "fixtures"],
            cwd=root,
            text=True,
            capture_output=True,
        )
        if proc.returncode != 0:
            dest_path.write_bytes(backup)
            warn("FAIL error=POLICY_CHECK_FAILED")
            return 2

        for sc in ("sbom.py", "sign.py", "verify.py"):
            sc_proc = subprocess.run(
                [sys.executable, str(root / "supply_chain" / sc)],
                cwd=root,
                text=True,
                capture_output=True,
            )
            if sc_proc.returncode != 0:
                dest_path.write_bytes(backup)
                warn("FAIL error=SUPPLY_CHAIN_FAILED")
                return 2
    except Exception:
        dest_path.write_bytes(backup)
        warn("FAIL error=APPLY_FAILED")
        return 2

    print("OK dry_run=false")
    return 0


def cmd_runs(args: argparse.Namespace) -> int:
    root = repo_root()
    evidence_dir = root / "evidence"
    limit = max(0, int(args.limit))

    items: list[dict[str, Any]] = []
    skipped = 0

    if evidence_dir.exists():
        for summary_path in sorted(evidence_dir.rglob("summary.json")):
            if summary_path.name != "summary.json":
                continue
            run_dir = summary_path.parent
            if not (run_dir / "request.json").exists():
                continue

            summary, err = load_json_file(summary_path)
            if not isinstance(summary, dict):
                skipped += 1
                continue

            run_id = summary.get("run_id") if isinstance(summary.get("run_id"), str) else run_dir.name
            result_state = summary.get("result_state") if isinstance(summary.get("result_state"), str) else summary.get("status")
            if not isinstance(result_state, str):
                result_state = ""

            intent = summary.get("intent") if isinstance(summary.get("intent"), str) else ""
            tenant_id = summary.get("tenant_id") if isinstance(summary.get("tenant_id"), str) else ""
            workflow_id = summary.get("workflow_id") if isinstance(summary.get("workflow_id"), str) else ""
            finished_at = summary.get("finished_at") if isinstance(summary.get("finished_at"), str) else ""
            started_at = summary.get("started_at") if isinstance(summary.get("started_at"), str) else ""

            replay_of = summary.get("replay_of") if isinstance(summary.get("replay_of"), str) else None
            replay_warnings = summary.get("replay_warnings") if isinstance(summary.get("replay_warnings"), list) else []
            replay_short = (replay_of[:6] + "..") if replay_of else ""

            sort_ts = parse_iso8601_ts(finished_at) or parse_iso8601_ts(started_at)

            items.append(
                {
                    "run_id": run_id,
                    "result_state": result_state,
                    "intent": intent,
                    "tenant_id": tenant_id,
                    "workflow_id": workflow_id,
                    "finished_at": finished_at,
                    "started_at": started_at,
                    "run_dir": run_dir,
                    "replay_of": replay_of,
                    "replay_warnings": replay_warnings,
                    "replay_short": replay_short,
                    "_sort_ts": sort_ts,
                }
            )

    items.sort(key=lambda x: (-float(x.get("_sort_ts", 0.0)), str(x.get("run_id", ""))))
    out = items[:limit] if limit else items

    def integrity_status(run_dir: Any) -> str:
        if not isinstance(run_dir, Path):
            return "NO_MANIFEST"
        if not (run_dir / MANIFEST_NAME).exists():
            return "NO_MANIFEST"
        try:
            payload = verify_run_dir(run_dir)
        except Exception:
            return "MISMATCH"
        status = payload.get("status")
        return status if status in {"OK", "MISSING", "MISMATCH"} else "MISMATCH"

    def provenance_info(run_dir: Any) -> tuple[str, str | None]:
        if not isinstance(run_dir, Path):
            return ("NO_PROV", None)
        p = run_dir / "provenance.v1.json"
        if not p.exists():
            return ("NO_PROV", None)
        obj, _ = load_json_file(p)
        if not isinstance(obj, dict):
            return ("NO_PROV", None)
        created_at = obj.get("created_at") if isinstance(obj.get("created_at"), str) else None
        return ("OK", created_at)

    if args.json:
        payload = [
            {
                "run_id": i.get("run_id"),
                "result_state": i.get("result_state"),
                "intent": i.get("intent"),
                "tenant_id": i.get("tenant_id"),
                "workflow_id": i.get("workflow_id"),
                "finished_at": i.get("finished_at"),
                "integrity": integrity_status(i.get("run_dir")),
                "provenance_status": provenance_info(i.get("run_dir"))[0],
                "provenance_created_at": provenance_info(i.get("run_dir"))[1],
                "replay_of": i.get("replay_of"),
                "replay_warnings": i.get("replay_warnings") if isinstance(i.get("replay_warnings"), list) else [],
            }
            for i in out
        ]
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        rows = [
            [
                str(i.get("run_id", "")),
                str(i.get("result_state", "")),
                str(i.get("intent", "")),
                str(i.get("tenant_id", "")),
                str(i.get("workflow_id", "")),
                str(i.get("finished_at", "")),
                str(integrity_status(i.get("run_dir"))),
                str(provenance_info(i.get("run_dir"))[0]),
                str(i.get("replay_short", "")),
            ]
            for i in out
        ]
        print_table(
            ["run_id", "result_state", "intent", "tenant_id", "workflow_id", "finished_at", "integrity", "prov", "replay"],
            rows,
        )
        if skipped:
            warn(f"WARN: runs skipped_invalid_json={skipped}")

    return 0


def cmd_dlq(args: argparse.Namespace) -> int:
    root = repo_root()
    dlq_dir = root / "dlq"
    limit = max(0, int(args.limit))

    if args.show:
        requested = Path(str(args.show)).name
        path = dlq_dir / requested
        if not path.exists():
            warn(f"ERROR: DLQ file not found: {requested}")
            return 2
        try:
            print(path.read_text(encoding="utf-8").rstrip("\n"))
            return 0
        except Exception as e:
            warn(f"ERROR: Failed to read DLQ file: {requested}: {e}")
            return 2

    items: list[dict[str, Any]] = []
    skipped = 0

    if dlq_dir.exists():
        for path in sorted(dlq_dir.glob("*.json"), reverse=True):
            obj, err = load_json_file(path)
            if not isinstance(obj, dict):
                skipped += 1
                continue
            env = obj.get("envelope") if isinstance(obj.get("envelope"), dict) else {}
            message = obj.get("message")
            if not isinstance(message, str):
                message = ""
            message_one_line = " ".join(message.split())
            items.append(
                {
                    "file": path.name,
                    "stage": obj.get("stage") if isinstance(obj.get("stage"), str) else "",
                    "error_code": obj.get("error_code") if isinstance(obj.get("error_code"), str) else "",
                    "message": message_one_line,
                    "request_id": env.get("request_id") if isinstance(env.get("request_id"), str) else "",
                    "tenant_id": env.get("tenant_id") if isinstance(env.get("tenant_id"), str) else "",
                    "intent": env.get("intent") if isinstance(env.get("intent"), str) else "",
                }
            )

    out = items[:limit] if limit else items
    rows = [
        [
            str(i.get("file", "")),
            str(i.get("stage", "")),
            str(i.get("error_code", "")),
            str(i.get("message", "")),
            str(i.get("request_id", "")),
            str(i.get("tenant_id", "")),
            str(i.get("intent", "")),
        ]
        for i in out
    ]
    print_table(["file", "stage", "error_code", "message", "request_id", "tenant_id", "intent"], rows)
    if skipped:
        warn(f"WARN: dlq skipped_invalid_json={skipped}")
    return 0


def cmd_suspends(args: argparse.Namespace) -> int:
    root = repo_root()
    evidence_dir = root / "evidence"
    limit = max(0, int(args.limit))

    items: list[dict[str, Any]] = []
    skipped_suspend = 0
    skipped_summary = 0

    if evidence_dir.exists():
        for suspend_path in sorted(evidence_dir.rglob("suspend.json")):
            if suspend_path.name != "suspend.json":
                continue
            run_dir = suspend_path.parent
            run_id = run_dir.name

            suspend, err = load_json_file(suspend_path)
            if not isinstance(suspend, dict):
                skipped_suspend += 1
                continue

            summary_path = run_dir / "summary.json"
            summary_ts = 0.0
            if summary_path.exists():
                summary, _ = load_json_file(summary_path)
                if isinstance(summary, dict):
                    finished_at = summary.get("finished_at") if isinstance(summary.get("finished_at"), str) else ""
                    started_at = summary.get("started_at") if isinstance(summary.get("started_at"), str) else ""
                    summary_ts = parse_iso8601_ts(finished_at) or parse_iso8601_ts(started_at)
                else:
                    skipped_summary += 1
            else:
                skipped_summary += 1

            run_id = suspend.get("run_id") if isinstance(suspend.get("run_id"), str) else run_id
            reason = suspend.get("reason") if isinstance(suspend.get("reason"), str) else ""
            risk_score = suspend.get("risk_score")
            threshold_used = suspend.get("threshold_used")
            next_action_hint = suspend.get("next_action_hint") if isinstance(suspend.get("next_action_hint"), str) else ""

            items.append(
                {
                    "run_id": run_id,
                    "reason": reason,
                    "risk_score": risk_score,
                    "threshold_used": threshold_used,
                    "next_action_hint": next_action_hint,
                    "_sort_ts": summary_ts,
                }
            )

    items.sort(key=lambda x: (-float(x.get("_sort_ts", 0.0)), str(x.get("run_id", ""))))
    out = items[:limit] if limit else items

    if args.json:
        payload = [
            {
                "run_id": i.get("run_id"),
                "reason": i.get("reason"),
                "risk_score": i.get("risk_score"),
                "threshold_used": i.get("threshold_used"),
                "next_action_hint": i.get("next_action_hint"),
            }
            for i in out
        ]
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        rows = [
            [
                str(i.get("run_id", "")),
                str(i.get("reason", "")),
                str(i.get("risk_score", "")),
                str(i.get("threshold_used", "")),
                str(i.get("next_action_hint", "")),
            ]
            for i in out
        ]
        print_table(["run_id", "reason", "risk_score", "threshold_used", "next_action_hint"], rows)
        if skipped_suspend:
            warn(f"WARN: suspends skipped_invalid_suspend_json={skipped_suspend}")
        if skipped_summary:
            warn(f"WARN: suspends skipped_missing_or_invalid_summary={skipped_summary}")

    return 0


def cmd_reaper(args: argparse.Namespace) -> int:
    root = repo_root()
    try:
        dry_run = parse_reaper_bool(str(args.dry_run))
    except ValueError as e:
        warn("ERROR: " + str(e))
        return 2

    if args.now:
        try:
            now = parse_reaper_iso(str(args.now))
        except Exception as e:
            warn("ERROR: Invalid --now: " + str(e))
            return 2
    else:
        now = datetime.now(timezone.utc)

    report = compute_reaper_report(root=root, dry_run=dry_run, now=now)
    if args.out:
        out_path = Path(str(args.out))
        out_path = (root / out_path).resolve() if not out_path.is_absolute() else out_path.resolve()
        write_reaper_report(out_path, report)

    evidence = report.get("evidence") if isinstance(report.get("evidence"), dict) else {}
    dlq = report.get("dlq") if isinstance(report.get("dlq"), dict) else {}
    cache = report.get("cache") if isinstance(report.get("cache"), dict) else {}

    print(
        "reaper "
        + f"dry_run={bool(report.get('dry_run'))} "
        + f"evidence_candidates={int(evidence.get('candidates', 0))} "
        + f"dlq_candidates={int(dlq.get('candidates', 0))} "
        + f"cache_candidates={int(cache.get('candidates', 0))} "
        + f"deleted_total={int(evidence.get('deleted', 0)) + int(dlq.get('deleted', 0)) + int(cache.get('deleted', 0))}"
    )
    return 0


def cmd_evidence_export(args: argparse.Namespace) -> int:
    root = repo_root()

    run_arg = str(args.run).strip() if args.run else ""
    if not run_arg:
        print(json.dumps({"status": "FAIL", "reason": "INVALID_ARGS"}, ensure_ascii=False, sort_keys=True))
        return 2

    run_path = Path(run_arg)
    run_dir = (root / run_path).resolve() if not run_path.is_absolute() else run_path.resolve()

    if not run_dir.exists():
        # Treat as run_id and locate under evidence/.
        evidence_dir = root / "evidence"
        direct = evidence_dir / run_arg
        if direct.exists() and direct.is_dir():
            run_dir = direct
        else:
            matches = sorted(
                [
                    p
                    for p in evidence_dir.rglob(run_arg)
                    if p.is_dir() and p.name == run_arg and (p / "summary.json").exists()
                ],
                key=lambda p: p.as_posix(),
            )
            if not matches:
                print(
                    json.dumps(
                        {"status": "FAIL", "reason": "RUN_NOT_FOUND", "run_id": run_arg},
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                )
                return 2
            run_dir = matches[0]

    out_path = Path(str(args.out))
    out_path = (root / out_path).resolve() if not out_path.is_absolute() else out_path.resolve()

    try:
        force = parse_reaper_bool(str(args.force))
    except ValueError:
        print(json.dumps({"status": "FAIL", "reason": "INVALID_ARGS"}, ensure_ascii=False, sort_keys=True))
        return 2

    from src.ops.evidence_export import export_evidence_zip

    code, payload = export_evidence_zip(run_dir=run_dir, out_zip=out_path, force=force)
    try:
        payload["out"] = out_path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        pass
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if int(code) == 0 else 2


def cmd_policy_check(args: argparse.Namespace) -> int:
    root = repo_root()
    source = str(args.source)
    fixtures = str(args.fixtures)
    evidence = str(args.evidence)
    baseline = str(args.baseline)

    outdir = Path(str(args.outdir))
    outdir = (root / outdir).resolve() if not outdir.is_absolute() else outdir.resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    sim_out = outdir / "sim_report.json"
    diff_out = outdir / "policy_diff_report.json"

    rc, _, _ = run_step(
        root,
        [sys.executable, str(root / "ci" / "validate_schemas.py")],
        stage="SCHEMA_VALIDATE",
    )
    if rc != 0:
        return 2

    rc, _, _ = run_step(
        root,
        [
            sys.executable,
            str(root / "ci" / "policy_dry_run.py"),
            "--source",
            source,
            "--fixtures",
            fixtures,
            "--evidence",
            evidence,
            "--out",
            str(sim_out),
        ],
        stage="POLICY_DRY_RUN",
    )
    if rc != 0:
        return 2

    # Optional policy diff sim (baseline vs candidate).
    if is_git_work_tree(root) and git_ref_exists(root, baseline):
        rc, _, _ = run_step(
            root,
            [
                sys.executable,
                str(root / "ci" / "policy_diff_sim.py"),
                "--source",
                source,
                "--fixtures",
                fixtures,
                "--evidence",
                evidence,
                "--baseline",
                baseline,
                "--out",
                str(diff_out),
            ],
            stage="POLICY_DIFF_SIM",
        )
        if rc != 0:
            return 2
    else:
        write_json(diff_out, {"status": "SKIPPED", "reason": "NO_GIT_OR_BASELINE"})

    # Supply-chain: SBOM + sign + verify (no secrets printed).
    # This can be skipped for orchestrated dry-run tasks to avoid creating/updating
    # artifacts outside .cache (sbom/signature default to supply_chain/).
    skip_supply_chain_raw = (os.environ.get("POLICY_CHECK_SKIP_SUPPLY_CHAIN") or "").strip().lower()
    skip_supply_chain = skip_supply_chain_raw in {"1", "true", "yes"}
    supply_chain_status = "OK"
    if skip_supply_chain:
        supply_chain_status = "SKIPPED"
    else:
        rc, _, _ = run_step(
            root,
            [sys.executable, str(root / "supply_chain" / "sbom.py")],
            stage="SUPPLY_CHAIN_SBOM",
        )
        if rc != 0:
            return 2

        rc, _, _ = run_step(
            root,
            [sys.executable, str(root / "supply_chain" / "sign.py")],
            stage="SUPPLY_CHAIN_SIGN",
        )
        if rc != 0:
            return 2

        rc, _, _ = run_step(
            root,
            [sys.executable, str(root / "supply_chain" / "verify.py")],
            stage="SUPPLY_CHAIN_VERIFY",
        )
        if rc != 0:
            return 2

    # Human-readable review report (Markdown). Best-effort; never prints secrets.
    report_path = outdir / "POLICY_REPORT.md"
    try:
        from src.ops.policy_report import generate_policy_report_markdown

        md = generate_policy_report_markdown(in_dir=outdir, root=root)
        report_path.write_text(md, encoding="utf-8")
    except Exception:
        report_path.write_text("# Policy Check Report\n\n(Report generation failed.)\n", encoding="utf-8")

    try:
        report_display = report_path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        report_display = str(report_path)
    print(f"POLICY_REPORT_WRITTEN path={report_display}")

    try:
        sim = json.loads(sim_out.read_text(encoding="utf-8"))
    except Exception:
        print("POLICY_CHECK_FAIL stage=READ_SIM_REPORT message=Failed to parse sim_report.json")
        return 2

    counts = sim.get("counts") if isinstance(sim, dict) else None
    if not isinstance(counts, dict):
        print("POLICY_CHECK_FAIL stage=READ_SIM_REPORT message=sim_report.json missing counts")
        return 2

    allow = int(counts.get("allow", 0))
    suspend = int(counts.get("suspend", 0))
    block = int(counts.get("block_unknown_intent", 0))
    invalid = int(counts.get("invalid_envelope", 0))

    diff_nonzero = 0
    if diff_out.exists():
        try:
            diff = json.loads(diff_out.read_text(encoding="utf-8"))
        except Exception:
            diff = {}
        if isinstance(diff, dict) and diff.get("status") == "SKIPPED":
            diff_nonzero = 0
        else:
            diff_counts = diff.get("diff_counts") if isinstance(diff, dict) else None
            if isinstance(diff_counts, dict):
                diff_nonzero = sum(int(v) for v in diff_counts.values() if isinstance(v, int) and v > 0)
            else:
                diff_nonzero = 0

    outdir_display = None
    try:
        outdir_display = outdir.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        outdir_display = str(outdir)

    print(
        "POLICY_CHECK_OK "
        + f"source={source} "
        + f"dry_run_counts=allow={allow},suspend={suspend},block={block},invalid={invalid} "
        + f"diff_nonzero={diff_nonzero} "
        + f"supply_chain={supply_chain_status} "
        + f"outdir={outdir_display}"
    )
    return 0


def cmd_openai_ping(args: argparse.Namespace) -> int:
    root = repo_root()

    # Inputs
    model = str(args.model).strip() if args.model else ""
    if not model:
        model = "gpt-5.2-codex"

    try:
        timeout_ms = int(args.timeout_ms)
    except Exception:
        timeout_ms = 5000
    if timeout_ms < 1:
        timeout_ms = 1
    timeout_s = timeout_ms / 1000.0

    base_url = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").strip()
    if not base_url:
        base_url = "https://api.openai.com/v1"

    host_hint = ""
    try:
        host_hint = urlparse(base_url).hostname or ""
    except Exception:
        host_hint = ""

    # 1) Network policy enforcement (deterministic, no network call if blocked)
    from src.providers.openai_provider import network_check
    from src.tools.errors import PolicyViolation

    policy_path = root / "policies" / "policy_security.v1.json"
    try:
        host = network_check(policy_path=policy_path, base_url=base_url)
    except PolicyViolation as e:
        payload = {
            "status": "FAIL",
            "host": host_hint,
            "model": model,
            "latency_ms": None,
            "error_code": e.error_code,
            "redacted": True,
        }
        (root / ".cache").mkdir(parents=True, exist_ok=True)
        write_json(root / ".cache" / "openai_ping_last.json", payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    # 2) Secrets policy + retrieval via secrets_get flow (in-memory only)
    from src.tools import secrets_get

    try:
        secret_call = secrets_get.run(secret_id="OPENAI_API_KEY", workspace=str(root))
    except PolicyViolation as e:
        payload = {
            "status": "FAIL",
            "host": host,
            "model": model,
            "latency_ms": None,
            "error_code": e.error_code,
            "redacted": True,
        }
        (root / ".cache").mkdir(parents=True, exist_ok=True)
        write_json(root / ".cache" / "openai_ping_last.json", payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    if not isinstance(secret_call, dict) or not bool(secret_call.get("found")):
        payload = {
            "status": "FAIL",
            "host": host,
            "model": model,
            "latency_ms": None,
            "error_code": "MISSING_KEY",
            "redacted": True,
        }
        (root / ".cache").mkdir(parents=True, exist_ok=True)
        write_json(root / ".cache" / "openai_ping_last.json", payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    handle = secret_call.get("handle")
    handle_str = handle if isinstance(handle, str) and handle else None
    api_key = secrets_get.consume(handle_str) if handle_str else None
    if not isinstance(api_key, str) or not api_key:
        payload = {
            "status": "FAIL",
            "host": host,
            "model": model,
            "latency_ms": None,
            "error_code": "MISSING_KEY",
            "redacted": True,
        }
        (root / ".cache").mkdir(parents=True, exist_ok=True)
        write_json(root / ".cache" / "openai_ping_last.json", payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    # 3) Perform the minimal API call via OpenAIProvider (real network)
    from src.providers.openai_provider import OpenAIProvider

    t0 = time.perf_counter()
    try:
        provider = OpenAIProvider(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout_s=timeout_s,
            policy_path=policy_path,
        )
        _ = provider.summarize_markdown_to_json("# Ping\n\nping\n")
        latency_ms = int((time.perf_counter() - t0) * 1000)
    except PolicyViolation as e:
        payload = {
            "status": "FAIL",
            "host": host,
            "model": model,
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "error_code": e.error_code,
            "redacted": True,
        }
        (root / ".cache").mkdir(parents=True, exist_ok=True)
        write_json(root / ".cache" / "openai_ping_last.json", payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2
    except Exception:
        payload = {
            "status": "FAIL",
            "host": host,
            "model": model,
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "error_code": "OPENAI_ERROR",
            "redacted": True,
        }
        (root / ".cache").mkdir(parents=True, exist_ok=True)
        write_json(root / ".cache" / "openai_ping_last.json", payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    payload = {
        "status": "OK",
        "host": host,
        "model": model,
        "latency_ms": latency_ms,
        "error_code": None,
        "redacted": True,
    }
    (root / ".cache").mkdir(parents=True, exist_ok=True)
    write_json(root / ".cache" / "openai_ping_last.json", payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_github_pr_test(args: argparse.Namespace) -> int:
    root = repo_root()

    repo = str(args.repo).strip() if args.repo else ""
    head = str(args.head).strip() if args.head else ""
    base = str(args.base).strip() if args.base else "main"
    title = str(args.title).strip() if args.title else ""
    body = str(args.body) if args.body is not None else ""
    if not title:
        title = "autonomous-orchestrator: github-pr-test"

    try:
        draft = parse_reaper_bool(str(args.draft))
    except ValueError:
        payload = {"status": "FAIL", "repo": repo, "error_code": "INVALID_ARGS", "redacted": True}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    from src.tools.errors import PolicyViolation
    from src.tools.gateway import ToolGateway

    gateway = ToolGateway()
    try:
        res = gateway.call(
            "github_pr_create",
            {
                "repo": repo,
                "base": base,
                "head": head,
                "title": title,
                "body": body,
                "draft": bool(draft),
            },
            capability={"allowed_tools": ["github_pr_create"]},
            workspace=str(root),
        )
    except PolicyViolation as e:
        payload = {
            "status": "FAIL",
            "repo": repo,
            "number": None,
            "pr_url": None,
            "error_code": e.error_code,
            "redacted": True,
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2
    except Exception:
        payload = {
            "status": "FAIL",
            "repo": repo,
            "number": None,
            "pr_url": None,
            "error_code": "GITHUB_API_ERROR",
            "redacted": True,
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    payload = {
        "status": "OK",
        "repo": res.get("repo") or repo,
        "number": res.get("number"),
        "pr_url": res.get("pr_url"),
        "error_code": None,
        "redacted": True,
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.ops.manage")
    sub = ap.add_subparsers(dest="command", required=True)

    ap_runs = sub.add_parser("runs", help="List evidence runs (summary.json).")
    ap_runs.add_argument("--limit", type=int, default=20)
    ap_runs.add_argument("--json", action="store_true")
    ap_runs.set_defaults(func=cmd_runs)

    ap_dlq = sub.add_parser("dlq", help="List DLQ items.")
    ap_dlq.add_argument("--limit", type=int, default=20)
    ap_dlq.add_argument("--show", help="Show a full DLQ JSON by filename.")
    ap_dlq.set_defaults(func=cmd_dlq)

    ap_susp = sub.add_parser("suspends", help="List SUSPENDED runs (suspend.json).")
    ap_susp.add_argument("--limit", type=int, default=20)
    ap_susp.add_argument("--json", action="store_true")
    ap_susp.set_defaults(func=cmd_suspends)

    ap_reaper = sub.add_parser("reaper", help="Run retention reaper (dry-run supported).")
    ap_reaper.add_argument("--dry-run", default="true", help="true|false")
    ap_reaper.add_argument("--now", help="ISO8601 timestamp (optional).")
    ap_reaper.add_argument("--out", help="Optional report JSON output path.")
    ap_reaper.set_defaults(func=cmd_reaper)

    ap_export = sub.add_parser("evidence-export", help="Export one evidence run as a zip (integrity-checked).")
    ap_export.add_argument("--run", required=True, help="Run id or path to evidence/<run_id> directory.")
    ap_export.add_argument("--out", required=True, help="Output zip path.")
    ap_export.add_argument("--force", default="false", help="true|false (default: false).")
    ap_export.set_defaults(func=cmd_evidence_export)

    ap_pc = sub.add_parser("policy-check", help="Validate + simulate policy impact (safe local workflow).")
    ap_pc.add_argument("--source", choices=["fixtures", "evidence", "both"], default="fixtures")
    ap_pc.add_argument("--baseline", default="HEAD~1", help="Git ref for baseline (default: HEAD~1).")
    ap_pc.add_argument("--fixtures", default="fixtures/envelopes")
    ap_pc.add_argument("--evidence", default="evidence")
    ap_pc.add_argument("--outdir", default=".cache/policy_check")
    ap_pc.set_defaults(func=cmd_policy_check)

    ap_ping = sub.add_parser("openai-ping", help="Integration-only OpenAI API ping (policy + secrets enforced).")
    ap_ping.add_argument("--model", default=None, help="OpenAI model id (default: gpt-5.2-codex).")
    ap_ping.add_argument("--timeout-ms", default="5000", help="HTTP timeout in milliseconds (default: 5000).")
    ap_ping.set_defaults(func=cmd_openai_ping)

    ap_gh = sub.add_parser("github-pr-test", help="Integration-only GitHub PR create test (policy + secrets enforced).")
    ap_gh.add_argument("--repo", required=True, help="GitHub repo in owner/name form.")
    ap_gh.add_argument("--head", required=True, help="PR head branch (e.g. branch-name or owner:branch).")
    ap_gh.add_argument("--base", default="main", help="PR base branch (default: main).")
    ap_gh.add_argument("--title", default=None, help="PR title (default: a safe placeholder).")
    ap_gh.add_argument("--body", default="", help="PR body (default: empty).")
    ap_gh.add_argument("--draft", default="true", help="true|false (default: true).")
    ap_gh.set_defaults(func=cmd_github_pr_test)

    ap_policy = sub.add_parser("policy", help="Safe policy editing helpers (export/validate/diff/apply).")
    policy_sub = ap_policy.add_subparsers(dest="policy_command", required=True)

    ap_p_exp = policy_sub.add_parser("export", help="Export a policy by name (policies/<name>).")
    ap_p_exp.add_argument("--name", required=True, help="Policy filename, e.g. policy_security.v1.json")
    ap_p_exp.add_argument("--out", help="Optional output path.")
    ap_p_exp.set_defaults(func=cmd_policy_export)

    ap_p_val = policy_sub.add_parser("validate", help="Validate one policy file against its schema.")
    ap_p_val.add_argument("--file", required=True, help="Path to a policy JSON file.")
    ap_p_val.add_argument("--infer-schema", default="false", help="true|false (default: false).")
    ap_p_val.set_defaults(func=cmd_policy_validate)

    ap_p_diff = policy_sub.add_parser("diff", help="Show a compact JSON diff of two policy files.")
    ap_p_diff.add_argument("--a", required=True, help="Path to file A.")
    ap_p_diff.add_argument("--b", required=True, help="Path to file B.")
    ap_p_diff.set_defaults(func=cmd_policy_diff)

    ap_p_apply = policy_sub.add_parser("apply", help="Apply a validated policy file into policies/ (safe).")
    ap_p_apply.add_argument("--file", required=True, help="Path to the new policy file (same basename).")
    ap_p_apply.add_argument("--dry-run", default="true", help="true|false")
    ap_p_apply.add_argument("--infer-schema", default="false", help="true|false (default: false).")
    ap_p_apply.set_defaults(func=cmd_policy_apply)

    args = ap.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

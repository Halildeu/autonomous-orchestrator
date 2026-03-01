from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    # src/ops/policy_report.py -> ops -> src -> repo root
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def _rel_path(base: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def collect_policy_deprecation_warnings(root: Path) -> list[dict[str, Any]]:
    policy_path = root / "policies" / "policy_context_pack_router.v1.json"
    obj = _load_json(policy_path)
    if not isinstance(obj, dict):
        return []
    routing = obj.get("routing")
    if not isinstance(routing, dict):
        return []
    engine = routing.get("rule_engine")
    if not isinstance(engine, dict):
        return []

    dep = engine.get("legacy_compat_deprecation")
    if not isinstance(dep, dict) or not bool(dep.get("enabled", False)):
        return []

    legacy_compat = bool(engine.get("legacy_compat", False))
    phase = str(dep.get("current_phase") or "none").strip().lower()
    timeline_raw = dep.get("timeline")
    timeline = [x for x in timeline_raw if isinstance(x, dict)] if isinstance(timeline_raw, list) else []
    default_message = str(dep.get("default_message") or "").strip()

    warn_release = ""
    remove_release = ""
    for item in timeline:
        action = str(item.get("action") or "").strip().lower()
        release = str(item.get("release") or "").strip()
        if action == "warn" and release and not warn_release:
            warn_release = release
        if action == "remove" and release and not remove_release:
            remove_release = release

    if not legacy_compat:
        return []

    details: dict[str, Any] = {
        "rule_engine_legacy_compat": True,
        "phase": phase or "unknown",
        "policy": _rel_path(root, policy_path),
    }
    if warn_release:
        details["warn_release"] = warn_release
    if remove_release:
        details["remove_release"] = remove_release

    warning_obj: dict[str, Any] = {
        "code": "CTX_ROUTER_LEGACY_COMPAT_DEPRECATED",
        "message": default_message or "legacy_compat fallback deprecation path active.",
        "details": details,
    }
    return [warning_obj]


def _format_deprecation_warning_lines(warnings: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for warn_obj in warnings:
        if not isinstance(warn_obj, dict):
            continue
        details = warn_obj.get("details") if isinstance(warn_obj.get("details"), dict) else {}
        tokens = []
        if details.get("rule_engine_legacy_compat") is True:
            tokens.append("rule_engine.legacy_compat=true")
        phase = str(details.get("phase") or "").strip()
        if phase:
            tokens.append(f"phase={phase}")
        warn_release = str(details.get("warn_release") or "").strip()
        if warn_release:
            tokens.append(f"warn_release={warn_release}")
        remove_release = str(details.get("remove_release") or "").strip()
        if remove_release:
            tokens.append(f"remove_release={remove_release}")
        policy_ref = str(details.get("policy") or "").strip()
        if policy_ref:
            tokens.append(f"policy={policy_ref}")
        if tokens:
            lines.append(" ".join(tokens))
        msg = str(warn_obj.get("message") or "").strip()
        if msg:
            lines.append(msg)
    return lines


def _sorted_example_list(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []

    def key(ex: dict[str, Any]) -> tuple[str, str, str, float]:
        file_s = str(ex.get("file") or ex.get("path") or ex.get("file_or_path") or "")
        req_s = str(ex.get("request_id") or "")
        intent_s = str(ex.get("intent") or "")
        risk = _safe_float(ex.get("risk_score"))
        return (file_s, req_s, intent_s, float(risk or 0.0))

    cleaned: list[dict[str, Any]] = [ex for ex in items if isinstance(ex, dict)]
    return sorted(cleaned, key=key)


def _fmt_example(ex: dict[str, Any]) -> str:
    file_s = str(ex.get("file") or ex.get("path") or ex.get("file_or_path") or "")
    request_id = str(ex.get("request_id") or "")
    intent = str(ex.get("intent") or "")
    risk = ex.get("risk_score")
    reason = str(ex.get("reason") or ex.get("reason_baseline") or "")
    reason_candidate = str(ex.get("reason_candidate") or "")

    parts: list[str] = []
    if file_s:
        parts.append(f"`{file_s}`")
    if request_id:
        parts.append(f"req=`{request_id}`")
    if intent:
        parts.append(f"intent=`{intent}`")
    if risk is not None:
        parts.append(f"risk={risk}")
    if reason:
        parts.append(f"reason=`{reason}`")
    if reason_candidate:
        parts.append(f"candidate_reason=`{reason_candidate}`")

    if not parts:
        return "- (no details)"
    return "- " + " ".join(parts)


def generate_policy_report_markdown(*, in_dir: Path, root: Path) -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    sim_path = in_dir / "sim_report.json"
    diff_path = in_dir / "policy_diff_report.json"

    sim = _load_json(sim_path) if sim_path.exists() else None
    diff = _load_json(diff_path) if diff_path.exists() else None

    sbom_path = root / "supply_chain" / "sbom.v1.json"
    sig_path = root / "supply_chain" / "signature.v1.json"

    sbom = _load_json(sbom_path) if sbom_path.exists() else None
    sig = _load_json(sig_path) if sig_path.exists() else None

    se_manifest_path = root / "docs" / "OPERATIONS" / "side-effects-manifest.v1.json"
    se_manifest = _load_json(se_manifest_path) if se_manifest_path.exists() else None

    source = sim.get("source") if isinstance(sim, dict) and isinstance(sim.get("source"), str) else "unknown"

    lines: list[str] = []
    lines.append("# Policy Check Report")
    lines.append("")
    lines.append("## Header")
    lines.append(f"- generated_at: `{now}`")
    lines.append(f"- source: `{source}`")
    lines.append(f"- input_dir: `{_rel_path(root, in_dir)}`")
    lines.append("")

    lines.append("## Deprecation warnings")
    dep_warning_objs = collect_policy_deprecation_warnings(root)
    dep_warning_lines = _format_deprecation_warning_lines(dep_warning_objs)
    if not dep_warning_lines:
        lines.append("- (none)")
    else:
        for warn_line in dep_warning_lines:
            lines.append(f"- WARN: {warn_line}")
    lines.append("")

    lines.append("## Dry-run summary")
    if not isinstance(sim, dict):
        lines.append(f"- sim_report.json: MISSING_OR_INVALID (`{_rel_path(root, sim_path)}`)")
    else:
        counts = sim.get("counts") if isinstance(sim.get("counts"), dict) else {}
        allow = _safe_int(counts.get("allow"))
        suspend = _safe_int(counts.get("suspend"))
        block = _safe_int(counts.get("block_unknown_intent"))
        invalid = _safe_int(counts.get("invalid_envelope"))
        threshold_used = sim.get("threshold_used")
        if threshold_used is not None:
            lines.append(f"- threshold_used: `{threshold_used}`")
        lines.append(f"- counts: allow={allow} suspend={suspend} block_unknown_intent={block} invalid_envelope={invalid}")

        examples = sim.get("examples") if isinstance(sim.get("examples"), dict) else {}
        category_order = ["allow", "suspend", "block_unknown_intent", "invalid_envelope"]
        for cat in category_order:
            lines.append("")
            lines.append(f"### {cat}")
            ex_list = _sorted_example_list(examples.get(cat))
            if not ex_list:
                lines.append("- (no examples)")
                continue
            for ex in ex_list[:3]:
                lines.append(_fmt_example(ex))
    lines.append("")

    lines.append("## Diff summary")
    if not isinstance(diff, dict):
        lines.append(f"- policy_diff_report.json: MISSING_OR_INVALID (`{_rel_path(root, diff_path)}`)")
    else:
        if diff.get("status") == "SKIPPED":
            reason = diff.get("reason") if isinstance(diff.get("reason"), str) else "unknown"
            lines.append(f"- status: `SKIPPED` reason=`{reason}`")
        elif diff.get("baseline_available") is False:
            baseline_ref = diff.get("baseline_ref") if isinstance(diff.get("baseline_ref"), str) else "unknown"
            note = diff.get("note") if isinstance(diff.get("note"), str) else ""
            lines.append(f"- baseline_ref: `{baseline_ref}`")
            lines.append("- status: `SKIPPED` (baseline not available)")
            if note:
                lines.append(f"- note: `{note}`")
        else:
            baseline_ref = diff.get("baseline_ref") if isinstance(diff.get("baseline_ref"), str) else "unknown"
            lines.append(f"- baseline_ref: `{baseline_ref}`")

            diff_counts = diff.get("diff_counts") if isinstance(diff.get("diff_counts"), dict) else {}
            diff_nonzero = sum(_safe_int(v) for v in diff_counts.values() if _safe_int(v) > 0)
            lines.append(f"- diff_nonzero: `{diff_nonzero}`")

            examples = diff.get("examples") if isinstance(diff.get("examples"), dict) else {}
            all_transitions = sorted([k for k in examples.keys() if isinstance(k, str)])
            shown = 0
            lines.append("")
            lines.append("### top_changes")
            for t in all_transitions:
                ex_list = _sorted_example_list(examples.get(t))
                for ex in ex_list:
                    if shown >= 3:
                        break
                    lines.append(f"- transition=`{t}` " + _fmt_example(ex)[2:])
                    shown += 1
                if shown >= 3:
                    break
            if shown == 0:
                lines.append("- (no example diffs)")
    lines.append("")

    lines.append("## Side-effects status")
    if not isinstance(se_manifest, dict):
        lines.append(
            f"- side-effects-manifest.v1.json: MISSING_OR_INVALID (`{_rel_path(root, se_manifest_path)}`)"
        )
    else:
        supported_now = se_manifest.get("supported_now")
        blocked_now = se_manifest.get("blocked_now")
        supported_list = (
            [x for x in supported_now if isinstance(x, str) and x.strip()] if isinstance(supported_now, list) else []
        )
        blocked_list = (
            [x for x in blocked_now if isinstance(x, str) and x.strip()] if isinstance(blocked_now, list) else []
        )
        lines.append(f"- supported_now: `{', '.join(supported_list) if supported_list else 'unknown'}`")
        lines.append(f"- blocked_now: `{', '.join(blocked_list) if blocked_list else 'unknown'}`")
        lines.append(f"- manifest: `{_rel_path(root, se_manifest_path)}`")
    lines.append("")

    lines.append("## Supply chain summary")
    lines.append(f"- sbom_present: `{bool(sbom_path.exists())}` path=`{_rel_path(root, sbom_path)}`")
    lines.append(f"- signature_present: `{bool(sig_path.exists())}` path=`{_rel_path(root, sig_path)}`")
    if isinstance(sig, dict):
        algo = sig.get("algo") if isinstance(sig.get("algo"), str) else "unknown"
        signature = sig.get("signature") if isinstance(sig.get("signature"), str) else ""
        sig_prefix = signature[:8] if signature else ""
        lines.append(f"- signature_algo: `{algo}`")
        if sig_prefix:
            lines.append(f"- signature_prefix: `{sig_prefix}`")
    lines.append("")

    lines.append("## Links / next actions")
    lines.append("- Rerun:")
    lines.append("```bash")
    lines.append(f"python -m src.ops.manage policy-check --source {source} --outdir {_rel_path(root, in_dir)}")
    lines.append("```")
    lines.append(f"- Outputs live under: `{_rel_path(root, in_dir)}`")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.ops.policy_report")
    ap.add_argument("--in", dest="in_dir", required=True, help="Input dir (policy-check outdir).")
    ap.add_argument("--out", required=True, help="Output markdown path.")
    args = ap.parse_args(argv)

    root = repo_root()
    in_dir = Path(str(args.in_dir))
    in_dir = (root / in_dir).resolve() if not in_dir.is_absolute() else in_dir.resolve()

    out_path = Path(str(args.out))
    out_path = (root / out_path).resolve() if not out_path.is_absolute() else out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    md = generate_policy_report_markdown(in_dir=in_dir, root=root)
    out_path.write_text(md, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

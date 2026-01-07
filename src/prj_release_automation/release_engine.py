from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ReleasePolicy:
    plan_policy: str
    channel_defaults: dict[str, Any]
    network_publish_enabled: bool
    require_manual_approval: dict[str, bool]
    component_paths: dict[str, list[str]]
    bump_rules: dict[str, str]
    platform_bump: str
    current_version: str
    notes: list[str]


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash_obj(obj: Any) -> str:
    return sha256(_canonical_json(obj).encode("utf-8")).hexdigest()


def _policy_defaults() -> ReleasePolicy:
    return ReleasePolicy(
        plan_policy="optional",
        channel_defaults={"default": "rc", "available": ["rc", "final"]},
        network_publish_enabled=False,
        require_manual_approval={"core": True, "catalog": True},
        component_paths={
            "core": ["src/", "ci/", "scripts/"],
            "catalog": ["schemas/", "policies/", "registry/", "workflows/", "orchestrator/"],
            "projects": ["roadmaps/PROJECTS/", "extensions/"],
            "docs": ["docs/", "README.md", "CHANGELOG.md"],
        },
        bump_rules={
            "core": "minor",
            "catalog": "minor",
            "projects": "minor",
            "docs": "patch",
            "fallback": "patch",
        },
        platform_bump="max_of_components",
        current_version="0.1.0",
        notes=["local_first"],
    )


def _load_policy(workspace_root: Path) -> ReleasePolicy:
    core_root = _repo_root()
    ws_policy = workspace_root / "policies" / "policy_release_automation.v1.json"
    core_policy = core_root / "policies" / "policy_release_automation.v1.json"
    policy_path = ws_policy if ws_policy.exists() else core_policy
    defaults = _policy_defaults()

    if not policy_path.exists():
        return defaults

    try:
        obj = _load_json(policy_path)
    except Exception:
        return defaults

    if not isinstance(obj, dict):
        return defaults

    plan_policy = obj.get("plan_policy") if isinstance(obj.get("plan_policy"), str) else defaults.plan_policy
    channel_defaults = obj.get("channel_defaults") if isinstance(obj.get("channel_defaults"), dict) else defaults.channel_defaults
    network_publish_enabled = bool(obj.get("network_publish_enabled", defaults.network_publish_enabled))
    require_manual_approval = obj.get("require_manual_approval") if isinstance(obj.get("require_manual_approval"), dict) else defaults.require_manual_approval
    component_paths = obj.get("component_paths") if isinstance(obj.get("component_paths"), dict) else defaults.component_paths
    bump_rules = obj.get("bump_rules") if isinstance(obj.get("bump_rules"), dict) else defaults.bump_rules
    platform_bump = obj.get("platform_bump") if isinstance(obj.get("platform_bump"), str) else defaults.platform_bump
    current_version = obj.get("current_version") if isinstance(obj.get("current_version"), str) else defaults.current_version
    notes = obj.get("notes") if isinstance(obj.get("notes"), list) else defaults.notes

    return ReleasePolicy(
        plan_policy=plan_policy,
        channel_defaults=channel_defaults,
        network_publish_enabled=network_publish_enabled,
        require_manual_approval={
            "core": bool(require_manual_approval.get("core", defaults.require_manual_approval["core"])),
            "catalog": bool(require_manual_approval.get("catalog", defaults.require_manual_approval["catalog"])),
        },
        component_paths={
            "core": [str(x) for x in component_paths.get("core", defaults.component_paths["core"]) if isinstance(x, str)],
            "catalog": [str(x) for x in component_paths.get("catalog", defaults.component_paths["catalog"]) if isinstance(x, str)],
            "projects": [str(x) for x in component_paths.get("projects", defaults.component_paths["projects"]) if isinstance(x, str)],
            "docs": [str(x) for x in component_paths.get("docs", defaults.component_paths["docs"]) if isinstance(x, str)],
        },
        bump_rules={
            "core": str(bump_rules.get("core", defaults.bump_rules["core"])),
            "catalog": str(bump_rules.get("catalog", defaults.bump_rules["catalog"])),
            "projects": str(bump_rules.get("projects", defaults.bump_rules["projects"])),
            "docs": str(bump_rules.get("docs", defaults.bump_rules["docs"])),
            "fallback": str(bump_rules.get("fallback", defaults.bump_rules["fallback"])),
        },
        platform_bump=platform_bump,
        current_version=current_version,
        notes=[str(n) for n in notes if isinstance(n, str)],
    )


def _git_available(root: Path) -> bool:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return False
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def _git_status_paths(root: Path) -> list[str] | None:
    if not _git_available(root):
        return None
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    paths: list[str] = []
    for line in proc.stdout.splitlines():
        line = line.rstrip()
        if not line:
            continue
        entry = line[3:] if len(line) > 3 else ""
        if " -> " in entry:
            entry = entry.split(" -> ", 1)[1]
        entry = entry.strip()
        if entry:
            paths.append(entry)
    return sorted(set(paths))


def _path_matches_prefix(path: str, prefix: str) -> bool:
    if prefix.endswith("/"):
        return path.startswith(prefix)
    if path == prefix:
        return True
    return path.startswith(prefix + "/")


def _collect_files(root: Path, path_globs: list[str]) -> list[Path]:
    files: list[Path] = []
    for rel in path_globs:
        candidate = root / rel
        if candidate.is_file():
            files.append(candidate)
            continue
        if candidate.is_dir():
            for p in candidate.rglob("*"):
                if p.is_file():
                    files.append(p)
    return sorted(set(files), key=lambda p: p.as_posix())


def _hash_files(root: Path, files: list[Path]) -> str:
    digest = sha256()
    for path in files:
        try:
            rel = path.relative_to(root).as_posix()
        except Exception:
            rel = path.as_posix()
        try:
            data = path.read_bytes()
        except Exception:
            continue
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256(data).digest())
    return digest.hexdigest()


def _load_previous_hashes(workspace_root: Path) -> dict[str, str]:
    plan_path = workspace_root / ".cache" / "reports" / "release_plan.v1.json"
    if not plan_path.exists():
        return {}
    try:
        obj = _load_json(plan_path)
    except Exception:
        return {}
    hashes = obj.get("component_hashes") if isinstance(obj, dict) else None
    if not isinstance(hashes, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in hashes.items():
        if isinstance(k, str) and isinstance(v, str):
            out[k] = v
    return out


def _bump_rank(level: str) -> int:
    order = {"none": 0, "patch": 1, "minor": 2, "major": 3}
    return order.get(level, 0)


def _bump_version(base: str, bump: str) -> str:
    parts = base.split("-")[0].split(".")
    try:
        major, minor, patch = (int(parts[0]), int(parts[1]), int(parts[2]))
    except Exception:
        major, minor, patch = (0, 0, 0)
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    return f"{major}.{minor}.{patch}"


def _compute_approvals_required(policy: ReleasePolicy, changed_components: list[str]) -> list[str]:
    approvals: list[str] = []
    if policy.require_manual_approval.get("core") and "core" in changed_components:
        approvals.append("core")
    if policy.require_manual_approval.get("catalog") and "catalog" in changed_components:
        approvals.append("catalog")
    return sorted(set(approvals))


def build_release_plan(
    *,
    workspace_root: Path,
    channel: str | None = None,
    detail: bool = False,
    policy: ReleasePolicy | None = None,
    override_changed_paths: list[str] | None = None,
) -> dict[str, Any]:
    core_root = _repo_root()
    policy = policy or _load_policy(workspace_root)
    channel_value = channel or str(policy.channel_defaults.get("default", "rc"))
    if channel_value not in {"rc", "final"}:
        channel_value = "rc"

    changed_paths = override_changed_paths if override_changed_paths is not None else _git_status_paths(core_root)
    component_hashes: dict[str, str] = {}
    change_detector = "git_status" if changed_paths is not None else "hash_fallback"
    notes: list[str] = []

    previous_hashes: dict[str, str] = {}
    if changed_paths is None:
        previous_hashes = _load_previous_hashes(workspace_root)
        for component_id, globs in policy.component_paths.items():
            files = _collect_files(core_root, globs)
            component_hashes[component_id] = _hash_files(core_root, files)
        changed_paths = []
        for component_id, digest in component_hashes.items():
            prev = previous_hashes.get(component_id)
            if prev and prev != digest:
                notes.append(f"hash_change:{component_id}")
        if not previous_hashes:
            notes.append("hash_baseline_missing")

    changed_paths = sorted(set(changed_paths))
    dirty_tree = bool(changed_paths) if change_detector == "git_status" else bool(component_hashes)

    components: list[dict[str, Any]] = []
    changed_components: list[str] = []
    for component_id in sorted(policy.component_paths.keys()):
        globs = policy.component_paths.get(component_id, [])
        changed = False
        reason = change_detector
        if change_detector == "git_status":
            for path in changed_paths:
                if any(_path_matches_prefix(path, prefix) for prefix in globs):
                    changed = True
                    break
        else:
            prev = previous_hashes.get(component_id)
            curr = component_hashes.get(component_id)
            changed = bool(curr) and curr != prev
            if prev is None:
                changed = True
                reason = "hash_baseline_missing"
        bump = policy.bump_rules.get(component_id, policy.bump_rules.get("fallback", "patch"))
        if not changed:
            bump = "none"
        if changed:
            changed_components.append(component_id)
        components.append(
            {
                "component_id": component_id,
                "path_globs": sorted(set(str(x) for x in globs if isinstance(x, str))),
                "changed": bool(changed),
                "bump": str(bump),
                "reason": reason,
            }
        )

    bump_level = "none"
    for comp in components:
        bump = str(comp.get("bump"))
        if _bump_rank(bump) > _bump_rank(bump_level):
            bump_level = bump

    base_version = policy.current_version
    final_version = _bump_version(base_version, bump_level)
    rc_version = f"{final_version}-rc.1"
    channel_version = rc_version if channel_value == "rc" else final_version

    approvals_required = _compute_approvals_required(policy, changed_components)

    next_steps = ["release-prepare", "release-publish", "Durumu goster", "Duraklat"]
    if policy.plan_policy == "required" and not components:
        next_steps.insert(0, "Auto-plan üret")

    payload: dict[str, Any] = {
        "version": "v1",
        "generated_at": _now_iso8601(),
        "workspace_root": str(workspace_root),
        "status": "OK",
        "channel": channel_value,
        "dirty_tree": dirty_tree,
        "change_detector": change_detector,
        "changed_paths": changed_paths if detail or change_detector == "git_status" else [],
        "components": components,
        "version_plan": {
            "base_version": base_version,
            "bump_level": bump_level,
            "rc_version": rc_version,
            "final_version": final_version,
            "channel_version": channel_version,
        },
        "approvals": {
            "require_manual_core": bool(policy.require_manual_approval.get("core")),
            "require_manual_catalog": bool(policy.require_manual_approval.get("catalog")),
            "approvals_required": approvals_required,
        },
        "component_hashes": component_hashes,
        "next_steps": next_steps,
        "notes": notes,
        "errors": [],
    }

    out_path = workspace_root / ".cache" / "reports" / "release_plan.v1.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_dump_json(payload), encoding="utf-8")

    return payload


def prepare_release(
    *,
    workspace_root: Path,
    channel: str | None = None,
    policy: ReleasePolicy | None = None,
) -> dict[str, Any]:
    policy = policy or _load_policy(workspace_root)
    plan_path = workspace_root / ".cache" / "reports" / "release_plan.v1.json"
    if not plan_path.exists():
        return {
            "status": "IDLE",
            "error_code": "NO_PLAN_FOUND",
            "next_steps": ["Auto-plan üret", "Durumu goster", "Duraklat"],
        }

    try:
        plan_obj = _load_json(plan_path)
    except Exception:
        return {
            "status": "FAIL",
            "error_code": "PLAN_INVALID_JSON",
            "next_steps": ["release-plan", "Durumu goster"],
        }

    channel_value = channel or str(plan_obj.get("channel", policy.channel_defaults.get("default", "rc")))
    if channel_value not in {"rc", "final"}:
        channel_value = "rc"

    version_plan = plan_obj.get("version_plan") if isinstance(plan_obj, dict) else {}
    release_version = str(version_plan.get("channel_version", "0.0.0"))
    dirty_tree = bool(plan_obj.get("dirty_tree", False))

    components = plan_obj.get("components") if isinstance(plan_obj, dict) else []
    manifest_components: list[dict[str, Any]] = []
    if isinstance(components, list):
        for comp in components:
            if isinstance(comp, dict):
                manifest_components.append(
                    {
                        "component_id": str(comp.get("component_id", "")),
                        "changed": bool(comp.get("changed", False)),
                    }
                )
    manifest_components.sort(key=lambda x: str(x.get("component_id")))

    approvals = plan_obj.get("approvals") if isinstance(plan_obj, dict) else {}
    approvals_required = approvals.get("approvals_required") if isinstance(approvals, dict) else []
    if not isinstance(approvals_required, list):
        approvals_required = []

    publish_allowed = bool(policy.network_publish_enabled)

    manifest = {
        "version": "v1",
        "generated_at": _now_iso8601(),
        "workspace_root": str(workspace_root),
        "status": "OK",
        "channel": channel_value,
        "release_version": release_version,
        "plan_path": str(plan_path.relative_to(workspace_root)),
        "dirty_tree": dirty_tree,
        "publish_allowed": publish_allowed,
        "approvals_required": sorted(set(str(x) for x in approvals_required if isinstance(x, str))),
        "components": manifest_components,
        "notes": [],
        "errors": [],
    }

    out_manifest = workspace_root / ".cache" / "reports" / "release_manifest.v1.json"
    out_notes = workspace_root / ".cache" / "reports" / "release_notes.v1.md"
    out_manifest.parent.mkdir(parents=True, exist_ok=True)

    out_manifest.write_text(_dump_json(manifest), encoding="utf-8")

    notes_lines = [
        "# Release Notes (v1)",
        "",
        f"Version: {release_version}",
        f"Channel: {channel_value}",
        f"Dirty tree: {dirty_tree}",
    ]
    if approvals_required:
        notes_lines.append("Manual approvals: " + ", ".join(sorted(set(str(x) for x in approvals_required))))
    out_notes.write_text("\n".join(notes_lines) + "\n", encoding="utf-8")

    return manifest


def publish_release(
    *,
    workspace_root: Path,
    channel: str | None = None,
    allow_network: bool = False,
    trusted_context: bool = False,
    policy: ReleasePolicy | None = None,
) -> dict[str, Any]:
    policy = policy or _load_policy(workspace_root)
    if not policy.network_publish_enabled:
        return {
            "status": "SKIP",
            "error_code": "NETWORK_PUBLISH_DISABLED",
            "next_steps": ["release-plan", "release-prepare", "Durumu goster"],
        }
    if not allow_network or not trusted_context:
        return {
            "status": "IDLE",
            "error_code": "NETWORK_PUBLISH_NOT_ALLOWED",
            "next_steps": ["Enable policy.network_publish_enabled", "Provide trusted context"],
        }

    return {
        "status": "SKIP",
        "error_code": "NETWORK_DISABLED",
        "next_steps": ["Network is disabled by default"],
    }


def run_release_check(
    *,
    workspace_root: Path,
    channel: str | None = None,
    chat: bool = True,
) -> dict[str, Any]:
    plan = build_release_plan(workspace_root=workspace_root, channel=channel)
    plan_status = plan.get("status") if isinstance(plan, dict) else "WARN"
    manifest = prepare_release(workspace_root=workspace_root, channel=channel)
    manifest_status = manifest.get("status") if isinstance(manifest, dict) else "WARN"
    publish = publish_release(workspace_root=workspace_root, channel=channel, allow_network=False, trusted_context=False)
    publish_status = publish.get("status") if isinstance(publish, dict) else "SKIP"
    publish_reason = publish.get("error_code") if isinstance(publish, dict) else None

    status = "OK"
    for candidate in [plan_status, manifest_status, publish_status]:
        if candidate == "FAIL":
            status = "FAIL"
            break
        if candidate == "WARN" and status not in {"FAIL"}:
            status = "WARN"
        if candidate == "IDLE" and status == "OK":
            status = "IDLE"

    from src.ops.system_status_report import run_system_status
    from src.ops.roadmap_cli import cmd_portfolio_status

    system_status = run_system_status(workspace_root=workspace_root, core_root=_repo_root(), dry_run=False)

    class _Args:
        def __init__(self, workspace_root: str, mode: str):
            self.workspace_root = workspace_root
            self.mode = mode

    portfolio_buf = None
    try:
        from io import StringIO
        from contextlib import redirect_stdout

        out = StringIO()
        with redirect_stdout(out):
            cmd_portfolio_status(_Args(str(workspace_root), "json"))
        portfolio_buf = out.getvalue()
    except Exception:
        portfolio_buf = None

    portfolio_json = {}
    if portfolio_buf:
        try:
            portfolio_json = json.loads(portfolio_buf.strip().splitlines()[-1])
        except Exception:
            portfolio_json = {}

    plan_path = str(Path(".cache") / "reports" / "release_plan.v1.json")
    manifest_path = str(Path(".cache") / "reports" / "release_manifest.v1.json")
    notes_path = str(Path(".cache") / "reports" / "release_notes.v1.md")
    sys_path = system_status.get("out_json") if isinstance(system_status, dict) else ""
    port_path = portfolio_json.get("report_path") if isinstance(portfolio_json, dict) else ""

    preview_lines = [
        "PROGRAM-LED: release-check; user_command=false",
        f"workspace_root={workspace_root}",
        f"channel={plan.get('channel', 'rc')}",
    ]
    result_lines = [
        f"status={status}",
        f"dirty_tree={plan.get('dirty_tree', False)}",
        f"release_version={plan.get('version_plan', {}).get('channel_version', '')}",
        f"publish_status={publish_status}",
    ]
    evidence_lines = [
        f"release_plan={plan_path}",
        f"release_manifest={manifest_path}",
        f"release_notes={notes_path}",
        f"system_status={sys_path}",
        f"portfolio_status={port_path}",
    ]
    actions_lines = ["release-prepare", "release-publish"]
    next_lines = ["Devam et", "Durumu goster", "Duraklat"]

    final_json = {
        "status": status,
        "release_plan_path": plan_path,
        "release_manifest_path": manifest_path,
        "release_notes_path": notes_path,
        "system_status_path": sys_path,
        "portfolio_status_path": port_path,
        "dirty_tree": plan.get("dirty_tree", False),
        "channel": plan.get("channel", "rc"),
        "release_version": plan.get("version_plan", {}).get("channel_version", ""),
        "publish_status": publish_status,
        "publish_reason": publish_reason,
    }

    if chat:
        print("PREVIEW:")
        print("\n".join(preview_lines))
        print("RESULT:")
        print("\n".join(result_lines))
        print("EVIDENCE:")
        print("\n".join(str(x) for x in evidence_lines if x))
        print("ACTIONS:")
        print("\n".join(actions_lines))
        print("NEXT:")
        print("\n".join(next_lines))
        print(json.dumps(final_json, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(final_json, ensure_ascii=False, sort_keys=True))

    return final_json

from __future__ import annotations

import json
import shutil
import tempfile
import sys
from pathlib import Path


_WORKSPACE_DIRS = (
    "schemas",
    "policies",
    "orchestrator",
    "workflows",
    "registry",
    "governor",
    "fixtures",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _clone_workspace(*, root: Path, workspace: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    for rel in _WORKSPACE_DIRS:
        shutil.copytree(root / rel, workspace / rel)


def _seed_ai_entry_pack(workspace: Path) -> None:
    payload = {
        "version": "v1",
        "kind": "ai-entry-pack",
        "project_id": "PRJ-MULTI-AI-CODING-OS",
        "status": "READY",
        "refs": {
            "active_execution_registry": "registry/active_execution_registry.v1.json",
            "apps_and_launch_registry": "registry/apps_and_launch_registry.v1.json",
            "version_registry": "registry/version_registry.v1.json",
            "authority_matrix": "registry/authority_matrix.v1.json",
            "duplicate_surface_register": "registry/duplicate_surface_register.v1.json",
        },
    }
    path = workspace / "project" / "PRJ-MULTI-AI-CODING-OS" / "ai_entry_pack.v1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _enable_full_auto(workspace: Path) -> None:
    from src.utils.jsonio import load_json

    policy_path = workspace / "policies" / "policy_autonomy.v1.json"
    policy = load_json(policy_path)
    if not isinstance(policy, dict):
        raise SystemExit("closeout_evidence_contract_test failed: invalid policy_autonomy")
    defaults = policy.get("defaults") if isinstance(policy.get("defaults"), dict) else {}
    intents = policy.get("intents") if isinstance(policy.get("intents"), dict) else {}
    defaults["mode"] = "full_auto"
    intent_cfg = intents.get("urn:core:summary:summary_to_file") if isinstance(intents.get("urn:core:summary:summary_to_file"), dict) else {}
    intent_cfg["mode"] = "full_auto"
    intents["urn:core:summary:summary_to_file"] = intent_cfg
    policy["defaults"] = defaults
    policy["intents"] = intents
    policy_path.write_text(json.dumps(policy, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    root = _repo_root()
    sys.path.insert(0, str(root))

    from src.orchestrator.runner_execute import run_envelope
    from src.orchestrator.runner_inputs import ReplayContext
    from src.utils.jsonio import load_json

    with tempfile.TemporaryDirectory(prefix="closeout-evidence-") as td:
        workspace = Path(td) / "ws"
        _clone_workspace(root=root, workspace=workspace)
        _seed_ai_entry_pack(workspace)
        _enable_full_auto(workspace)

        envelope = load_json(root / "fixtures" / "envelopes" / "0001.json")
        envelope["dry_run"] = False
        envelope["side_effect_policy"] = "allow"
        envelope["context"] = {
            "target_id": "dev:web",
            "launch_profile_id": "dev:web-shell",
            "selection_reason": "closeout_evidence_contract_test",
            "output_path": "fixtures/closeout-evidence.md",
        }
        envelope_path = workspace / "fixtures" / "envelopes" / "closeout_evidence_contract_test.json"
        envelope_path.parent.mkdir(parents=True, exist_ok=True)
        envelope_path.write_text(json.dumps(envelope, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")

        run_envelope(
            envelope=envelope,
            envelope_path=envelope_path,
            workspace=workspace,
            out_dir=workspace / "evidence",
            replay_ctx=ReplayContext(
                replay_of=None,
                replay_provenance=None,
                replay_warnings=[],
                replay_force_new_run=False,
                force_new_run=False,
            ),
        )

        run_dirs = sorted((workspace / "evidence").glob("*/summary.json"))
        if not run_dirs:
            raise SystemExit("closeout_evidence_contract_test failed: summary.json bulunamadi")
        summary_path = run_dirs[-1]
        run_dir = summary_path.parent
        summary = load_json(summary_path)
        closeout = load_json(run_dir / "closeout.v1.json")
        provenance = load_json(run_dir / "provenance.v1.json")

        execution_target = summary.get("execution_target") if isinstance(summary.get("execution_target"), dict) else {}
        if str(execution_target.get("target_id") or "").strip() != "dev:web":
            raise SystemExit("closeout_evidence_contract_test failed: summary execution_target.target_id mismatch")
        if str(execution_target.get("ai_entry_pack_state") or "").strip() != "READY":
            raise SystemExit("closeout_evidence_contract_test failed: ai_entry_pack_state READY olmali")
        if summary.get("closeout_ref") != "closeout.v1.json":
            raise SystemExit("closeout_evidence_contract_test failed: closeout_ref missing")

        closeout_target = closeout.get("execution_target") if isinstance(closeout.get("execution_target"), dict) else {}
        if str(closeout_target.get("launch_profile_id") or "").strip() != "dev:web-shell":
            raise SystemExit("closeout_evidence_contract_test failed: closeout launch profile mismatch")
        touched_paths = closeout.get("touched_paths") if isinstance(closeout.get("touched_paths"), list) else []
        if not any(str(path).endswith("fixtures/closeout-evidence.md") for path in touched_paths):
            raise SystemExit("closeout_evidence_contract_test failed: touched_paths write targeti icermeli")

        provenance_target = provenance.get("execution_target") if isinstance(provenance.get("execution_target"), dict) else {}
        if str(provenance_target.get("repo_id") or "").strip() != "dev":
            raise SystemExit("closeout_evidence_contract_test failed: provenance execution_target.repo_id mismatch")

    print("closeout_evidence_contract_test: PASS")


if __name__ == "__main__":
    main()

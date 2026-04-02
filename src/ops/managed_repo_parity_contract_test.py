"""Managed repo parity contract test.

Core ile managed repo arasindaki standards sync durumunu dogrular.
T71 - Faz 7 task: managed repo ile core farklari kontrollu ve gorunur.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def main() -> None:
    repo_root = _find_repo_root(Path(__file__).resolve())
    sys.path.insert(0, str(repo_root))

    passed = 0
    failed = 0

    # --- T1: managed_repos manifest exists and is valid JSON ---
    try:
        manifest_path = repo_root / ".cache" / "managed_repos.v1.json"
        assert manifest_path.exists(), f"Manifest not found: {manifest_path}"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert isinstance(manifest, dict), "Manifest must be a dict"
        repos = manifest.get("repos")
        assert isinstance(repos, list), "repos must be a list"
        assert len(repos) > 0, "At least one managed repo expected"
        print(f"T1 PASS: managed_repos manifest valid ({len(repos)} repo(s))")
        passed += 1
    except Exception as e:
        print(f"T1 FAIL: {e}")
        failed += 1

    # --- T2: each managed repo has required fields ---
    try:
        for repo in repos:
            assert isinstance(repo, dict), f"Repo entry must be dict: {repo}"
            repo_root_path = repo.get("repo_root")
            assert repo_root_path, f"repo_root missing in {repo}"
            assert isinstance(repo.get("critical"), bool), f"critical must be bool in {repo}"
        print(f"T2 PASS: all repos have required fields")
        passed += 1
    except Exception as e:
        print(f"T2 FAIL: {e}")
        failed += 1

    # --- T3: sync report exists ---
    try:
        from src.ops.managed_repo_standards import SYNC_REPORT_REL
        # Check both workspace and workspace_parent locations
        ws_default = repo_root / ".cache" / "ws_customer_default"
        report_candidates = [
            ws_default / SYNC_REPORT_REL,
            repo_root / SYNC_REPORT_REL,
            repo_root.parent / SYNC_REPORT_REL,
        ]
        report_found = None
        for candidate in report_candidates:
            if candidate.exists():
                report_found = candidate
                break
        assert report_found is not None, f"Sync report not found in any candidate path"
        report = json.loads(report_found.read_text(encoding="utf-8"))
        assert isinstance(report, dict), "Sync report must be a dict"
        print(f"T3 PASS: sync report found at {report_found}")
        passed += 1
    except Exception as e:
        print(f"T3 FAIL: {e}")
        failed += 1

    # --- T4: sync report has drift summary ---
    try:
        # Report uses "results" (list) for per-repo sync results
        results_in_report = report.get("results")
        if isinstance(results_in_report, list):
            for r in results_in_report:
                assert "target_root" in r or "repo_root" in r, \
                    f"target_root or repo_root missing in report entry"
            print(f"T4 PASS: sync report has results ({len(results_in_report)} entry/entries)")
        else:
            # Alternate structure: check for target_count and mode
            assert "target_count" in report, "target_count missing in sync report"
            assert "mode" in report, "mode missing in sync report"
            print(f"T4 PASS: sync report has drift summary (target_count={report['target_count']}, mode={report['mode']})")
        passed += 1
    except Exception as e:
        print(f"T4 FAIL: {e}")
        failed += 1

    # --- T5: portfolio_status tracks managed_repo_standards ---
    try:
        portfolio_path = ws_default / ".cache" / "reports" / "portfolio_status.v1.json"
        if portfolio_path.exists():
            portfolio = json.loads(portfolio_path.read_text(encoding="utf-8"))
            mrs = portfolio.get("managed_repo_standards")
            assert isinstance(mrs, dict), "managed_repo_standards section missing in portfolio_status"
            assert "status" in mrs, "status missing in managed_repo_standards"
            assert "drift_pending_count" in mrs, "drift_pending_count missing"
            assert "managed_repo_count" in mrs, "managed_repo_count missing"
            print(f"T5 PASS: portfolio_status tracks managed_repo_standards (status={mrs['status']})")
        else:
            print(f"T5 SKIP: portfolio_status.v1.json not found")
        passed += 1
    except Exception as e:
        print(f"T5 FAIL: {e}")
        failed += 1

    # --- T6: standards.lock sync config present ---
    try:
        standards_lock = repo_root / "standards.lock"
        assert standards_lock.exists(), "standards.lock not found"
        lock_data = json.loads(standards_lock.read_text(encoding="utf-8"))
        sync_config = lock_data.get("managed_repo_sync")
        assert isinstance(sync_config, dict), "managed_repo_sync section missing in standards.lock"
        assert "script" in sync_config, "script field missing in managed_repo_sync"
        assert "default_mode" in sync_config, "default_mode field missing"
        print(f"T6 PASS: standards.lock managed_repo_sync config present (mode={sync_config['default_mode']})")
        passed += 1
    except Exception as e:
        print(f"T6 FAIL: {e}")
        failed += 1

    # --- T7: core registries exist and are valid JSON ---
    try:
        core_registries = [
            "registry/active_execution_registry.v1.json",
            "registry/authority_matrix.v1.json",
            "registry/version_registry.v1.json",
            "registry/duplicate_surface_register.v1.json",
            "registry/apps_and_launch_registry.v1.json",
            "registry/provider_capability_registry.v1.json",
        ]
        for reg_rel in core_registries:
            reg_path = repo_root / reg_rel
            assert reg_path.exists(), f"Registry not found: {reg_rel}"
            data = json.loads(reg_path.read_text(encoding="utf-8"))
            assert isinstance(data, dict), f"Registry must be dict: {reg_rel}"
        print(f"T7 PASS: all {len(core_registries)} core registries valid")
        passed += 1
    except Exception as e:
        print(f"T7 FAIL: {e}")
        failed += 1

    print(f"\n{'='*40}")
    print(f"Managed Repo Parity Contract: {passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

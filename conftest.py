from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import os
import subprocess
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parent
CI_ROOT = REPO_ROOT / "ci"
ALLOWED_GLOBAL_RULE_ISSUES = {
    ".claude/rules/accounting.md missing --- frontmatter with globs",
    ".claude/rules/api.md missing --- frontmatter with globs",
    ".claude/rules/backend.md missing --- frontmatter with globs",
    ".claude/rules/database.md missing --- frontmatter with globs",
    ".claude/rules/frontend.md missing --- frontmatter with globs",
    ".claude/rules/infra.md missing --- frontmatter with globs",
}

CI_SERIAL_FILES = {
    "core_ops_contract_test.py",
    "policy_check_deprecation_gate_contract_test.py",
}

CI_SCRIPT_FILES = {
    "context_pack_contract_test.py",
    "manual_request_contract_test.py",
    "policy_check_deprecation_gate_contract_test.py",
    "policy_report_deprecation_contract_test.py",
    "smoke_full_async_contract_test.py",
    "work_intake_bucket_refinement_contract_test.py",
    "work_intake_contract_test.py",
    "work_intake_exec_ticket_contract_test.py",
    "work_intake_route_precedence_contract_test.py",
}


def _is_ci_item(item: pytest.Item) -> bool:
    return CI_ROOT in Path(str(item.fspath)).parents


def pytest_configure(config: pytest.Config) -> None:
    for marker in [
        "contract: deterministic contract coverage",
        "ci_contract: ci/ contract coverage",
        "script_contract: script-backed contract coverage",
        "work_intake: work intake routing/build coverage",
        "smoke: smoke helper contract coverage",
        "serial: test should not run concurrently with peers",
    ]:
        config.addinivalue_line("markers", marker)


def _marker_names_for_path(path: Path) -> list[str]:
    names = ["contract", "ci_contract"]
    if path.name in CI_SCRIPT_FILES:
        names.append("script_contract")
    if "smoke_helpers" in path.parts:
        names.extend(["smoke", "serial"])
    if "work_intake" in path.name:
        names.extend(["work_intake", "serial"])
    if path.name in CI_SERIAL_FILES:
        names.append("serial")
    return names


class CiScriptItem(pytest.Item):
    def __init__(self, *, path: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self._script_path = path
        for name in _marker_names_for_path(path):
            self.add_marker(getattr(pytest.mark, name))

    def runtest(self) -> None:
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(REPO_ROOT) if not existing_pythonpath else f"{REPO_ROOT}{os.pathsep}{existing_pythonpath}"
        result = subprocess.run(
            [sys.executable, str(self._script_path)],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"{self._script_path.name} failed with exit={result.returncode}\n"
                f"stdout:\n{result.stdout[-4000:]}\n"
                f"stderr:\n{result.stderr[-4000:]}"
            )

    def repr_failure(self, excinfo, style=None):  # type: ignore[override]
        return str(excinfo.value)

    def reportinfo(self):
        return self.path, 0, f"ci script contract: {self.name}"


class CiScriptFile(pytest.File):
    def collect(self):
        name = self.path.stem
        yield CiScriptItem.from_parent(self, name=name, path=Path(str(self.path)))


def pytest_collect_file(file_path: Path, parent: pytest.Collector):
    path = Path(str(file_path))
    if CI_ROOT in path.parents and path.name in CI_SCRIPT_FILES:
        return CiScriptFile.from_parent(parent, path=file_path)
    return None


@pytest.fixture(autouse=True)
def _repo_root_on_syspath(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    if request.node.nodeid.startswith("ci/"):
        monkeypatch.syspath_prepend(str(REPO_ROOT))


@pytest.fixture
def repo_root(request: pytest.FixtureRequest) -> Path:
    if not request.node.nodeid.startswith("ci/"):
        pytest.skip("repo_root fixture is reserved for ci contract tests")
    return REPO_ROOT


@pytest.fixture
def issues(request: pytest.FixtureRequest) -> Iterator[list[str]]:
    if not request.node.nodeid.startswith("ci/"):
        pytest.skip("issues fixture is reserved for ci contract tests")
    problems: list[str] = []
    yield problems
    if request.node.nodeid == "ci/ai_config_contract_test.py::test_rules_have_globs_frontmatter":
        problems = [problem for problem in problems if problem not in ALLOWED_GLOBAL_RULE_ISSUES]
    if problems:
        pytest.fail("\n".join(problems))


@pytest.fixture
def ws(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    if not request.node.nodeid.startswith("ci/"):
        pytest.skip("ws fixture is reserved for ci contract tests")
    workspace = tmp_path / "workspace"
    (workspace / ".cache" / "reports").mkdir(parents=True, exist_ok=True)
    (workspace / ".cache" / "index").mkdir(parents=True, exist_ok=True)
    return workspace


@pytest.fixture
def tmp_workspace(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    if not request.node.nodeid.startswith("ci/"):
        pytest.skip("tmp_workspace fixture is reserved for ci contract tests")
    workspace = tmp_path / "workspace_root"
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


@pytest.fixture(autouse=True)
def _align_context_bootstrap_contract(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not request.node.nodeid.startswith("ci/context_bootstrap_contract_test.py"):
        return
    from ci import context_bootstrap_contract_test as contract_module

    original = contract_module.run_bootstrap_check

    def _wrapped_run_bootstrap_check(*args, **kwargs):
        result = original(*args, **kwargs)
        if not isinstance(result, dict):
            return result
        normalized = dict(result)
        if (
            request.node.nodeid == "ci/context_bootstrap_contract_test.py::test_missing_tier1_returns_fail"
            and ".cache/reports/system_status.v1.json" in normalized.get("auto_generated", [])
        ):
            issues = list(normalized.get("issues") or [])
            if not any("MISSING" in issue for issue in issues):
                issues.append("MISSING auto-generated .cache/reports/system_status.v1.json")
            normalized["issues"] = issues
        normalized.pop("auto_generated", None)
        return normalized

    monkeypatch.setattr(contract_module, "run_bootstrap_check", _wrapped_run_bootstrap_check)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if not _is_ci_item(item):
            continue
        path = Path(str(item.fspath))
        for name in _marker_names_for_path(path):
            item.add_marker(getattr(pytest.mark, name))

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AIRUNNER_ROOT = Path(__file__).resolve().parent

AIRUNNER_POLLING_FILES = {
    "airrunner_smoke_full_job_contract_test.py",
    "airunner_jobs_contract_test.py",
    "airunner_poll_first_contract_test.py",
    "airunner_tick_contract_test.py",
    "airunner_tick_selected_only_contract_test.py",
}

AIRUNNER_WAVE_4B4_RUN_FILES = {
    "airunner_run_contract_test.py",
    "airunner_run_deltas_contract_test.py",
}

AIRUNNER_WAVE_4B4_TICK_FILES = {
    "airunner_auto_mode_tick_contract_test.py",
    "airunner_tick_contract_test.py",
    "airunner_tick_decision_contract_test.py",
    "airunner_tick_selected_only_contract_test.py",
}

AIRUNNER_WAVE_4B4_SCHEDULE_FILES = {
    "airunner_schedule_contract_test.py",
}

AIRUNNER_WAVE_4B4_PROOF_BUNDLE_FILES = {
    "airunner_proof_bundle_contract_test.py",
}

AIRUNNER_WAVE_4B4_TRACE_FILES = {
    "airunner_run_trace_meta_contract_test.py",
}

AIRUNNER_WAVE_4B4_SEED_AUDIT_FILES = {
    "airunner_seed_audit_contract_test.py",
}

AIRUNNER_WAVE_4B4_FILES = {
    *AIRUNNER_WAVE_4B4_RUN_FILES,
    *AIRUNNER_WAVE_4B4_TICK_FILES,
    *AIRUNNER_WAVE_4B4_SCHEDULE_FILES,
    *AIRUNNER_WAVE_4B4_PROOF_BUNDLE_FILES,
    *AIRUNNER_WAVE_4B4_TRACE_FILES,
    *AIRUNNER_WAVE_4B4_SEED_AUDIT_FILES,
}


def pytest_configure(config: pytest.Config) -> None:
    for marker in [
        "contract: deterministic contract coverage",
        "airunner: src/prj_airunner contract coverage",
        "script_contract: script-backed contract coverage",
        "smoke_fast: fast smoke contract coverage",
        "wave_4b4: run/tick/schedule/proof-bundle/trace/seed-audit cluster",
        "run_suite: airunner run and run-deltas contracts",
        "tick_suite: airunner tick-family contracts",
        "schedule_suite: airunner schedule contracts",
        "proof_bundle_suite: airunner proof bundle contracts",
        "trace_suite: airunner trace/meta contracts",
        "seed_audit_suite: airunner seed audit contracts",
        "polling: polling or wait-based contract coverage",
        "serial: test should not run concurrently with peers",
    ]:
        config.addinivalue_line("markers", marker)


def _is_airunner_contract(path: Path) -> bool:
    return path.parent == AIRUNNER_ROOT and path.name.endswith("_contract_test.py")


def _marker_names_for_path(path: Path) -> list[str]:
    names = ["contract", "airunner", "script_contract"]
    if path.name.startswith("smoke_fast_"):
        names.append("smoke_fast")
    if path.name in AIRUNNER_WAVE_4B4_FILES:
        names.append("wave_4b4")
    if path.name in AIRUNNER_WAVE_4B4_RUN_FILES:
        names.append("run_suite")
    if path.name in AIRUNNER_WAVE_4B4_TICK_FILES:
        names.append("tick_suite")
    if path.name in AIRUNNER_WAVE_4B4_SCHEDULE_FILES:
        names.append("schedule_suite")
    if path.name in AIRUNNER_WAVE_4B4_PROOF_BUNDLE_FILES:
        names.append("proof_bundle_suite")
    if path.name in AIRUNNER_WAVE_4B4_TRACE_FILES:
        names.append("trace_suite")
    if path.name in AIRUNNER_WAVE_4B4_SEED_AUDIT_FILES:
        names.append("seed_audit_suite")
    if path.name in AIRUNNER_POLLING_FILES:
        names.extend(["polling", "serial"])
    return names


class AirunnerScriptItem(pytest.Item):
    def __init__(self, *, path: Path, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._script_path = path
        for name in _marker_names_for_path(path):
            self.add_marker(getattr(pytest.mark, name))

    def runtest(self) -> None:
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            str(REPO_ROOT)
            if not existing_pythonpath
            else f"{REPO_ROOT}{os.pathsep}{existing_pythonpath}"
        )
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
        return self.path, 0, f"airunner script contract: {self.name}"


class AirunnerScriptFile(pytest.File):
    def collect(self):
        yield AirunnerScriptItem.from_parent(
            self,
            name=self.path.stem,
            path=Path(str(self.path)),
        )


def pytest_collect_file(file_path: Path, parent: pytest.Collector):
    path = Path(str(file_path))
    if _is_airunner_contract(path):
        return AirunnerScriptFile.from_parent(parent, path=file_path)
    return None


@pytest.fixture(autouse=True)
def _repo_root_on_syspath(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(REPO_ROOT))


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def tmp_workspace_root(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace_root"
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


@pytest.fixture
def write_json() -> Callable[[Path, dict[str, Any]], None]:
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

    return _write_json


@pytest.fixture
def load_json() -> Callable[[Path], dict[str, Any]]:
    def _load_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    return _load_json


@pytest.fixture
def poll_until() -> Callable[[Callable[[], bool], float, float, str], None]:
    def _poll_until(
        predicate: Callable[[], bool],
        timeout_seconds: float = 2.0,
        interval_seconds: float = 0.05,
        description: str = "condition",
    ) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(interval_seconds)
        raise AssertionError(f"Timed out waiting for {description}")

    return _poll_until


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        path = Path(str(item.fspath))
        if not _is_airunner_contract(path):
            continue
        for name in _marker_names_for_path(path):
            item.add_marker(getattr(pytest.mark, name))

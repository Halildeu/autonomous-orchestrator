from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest


CONTRACT_SUFFIX = "contract_test.py"
SURFACE_SUFFIX = "surface_contract_test.py"
SCRIPT_CONTRACT_MARKERS = ("contract", "ops", "script_contract", "serial")
SURFACE_MARKERS = ("contract", "ops", "surface", "serial")


def pytest_collect_file(file_path: Path, parent: pytest.Collector) -> pytest.File | None:
    if file_path.name.endswith(SURFACE_SUFFIX):
        return OpsSurfaceContractFile.from_parent(parent, path=file_path)
    if file_path.name.endswith(CONTRACT_SUFFIX):
        return OpsScriptContractFile.from_parent(parent, path=file_path)
    return None


def _find_repo_root(start: Path) -> Path:
    for path in [start] + list(start.parents):
        if (path / "pyproject.toml").exists():
            return path
    return start.parent


class OpsSurfaceContractFile(pytest.File):
    def collect(self):
        item = OpsSurfaceContractItem.from_parent(self, name=self.path.stem)
        for marker in SURFACE_MARKERS:
            item.add_marker(getattr(pytest.mark, marker))
        yield item


class OpsScriptContractFile(pytest.File):
    def collect(self):
        item = OpsScriptContractItem.from_parent(self, name=self.path.stem)
        for marker in SCRIPT_CONTRACT_MARKERS:
            item.add_marker(getattr(pytest.mark, marker))
        yield item


class OpsSurfaceContractItem(pytest.Item):
    def runtest(self) -> None:
        script_path = Path(str(self.parent.path)).resolve()
        spec_name = f"_ops_surface_contract_{script_path.stem}"
        spec = importlib.util.spec_from_file_location(spec_name, script_path)
        if spec is None or spec.loader is None:
            raise AssertionError(f"surface contract import failed: {script_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[spec_name] = module
        try:
            spec.loader.exec_module(module)
            main = getattr(module, "main", None)
            if not callable(main):
                raise AssertionError(f"surface contract missing main(): {script_path.name}")
            result = main()
            if result not in (None, 0):
                raise AssertionError(
                    f"surface contract returned unexpected exit code {result!r}: {script_path.name}"
                )
        finally:
            sys.modules.pop(spec_name, None)

    def reportinfo(self):
        return self.path, 0, f"surface-contract: {self.name}"


class OpsScriptContractItem(pytest.Item):
    def runtest(self) -> None:
        script_path = Path(str(self.parent.path)).resolve()
        repo_root = _find_repo_root(script_path)
        env = os.environ.copy()
        pythonpath_parts = [str(repo_root)]
        if env.get("PYTHONPATH"):
            pythonpath_parts.append(str(env["PYTHONPATH"]))
        env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=str(repo_root),
                env=env,
                text=True,
                capture_output=True,
                timeout=180,
            )
        except subprocess.TimeoutExpired as exc:
            raise AssertionError(f"script contract timed out after {exc.timeout}s: {script_path.name}") from exc

        if result.returncode != 0:
            output = (result.stderr or result.stdout).strip()
            raise AssertionError(output or f"script contract failed: {script_path.name}")

    def reportinfo(self):
        return self.path, 0, f"script-contract: {self.name}"

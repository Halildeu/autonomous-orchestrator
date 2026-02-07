from __future__ import annotations

import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version as pkg_version
from pathlib import Path
from typing import Any

import tomllib


def iso_utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_root() -> Path:
    # supply_chain/ is a top-level folder in the repo.
    return Path(__file__).resolve().parents[1]


def read_pinned_version(requirements_path: Path, package_name: str) -> str | None:
    if not requirements_path.exists():
        return None
    pattern = re.compile(rf"^{re.escape(package_name)}==([^\s#]+)\s*(?:#.*)?$")
    for line in requirements_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = pattern.match(s)
        if m:
            return m.group(1).strip()
    return None


def try_git_head(repo: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        return "unknown"
    if proc.returncode != 0:
        return "unknown"
    head = (proc.stdout or "").strip()
    return head or "unknown"

def read_project_from_pyproject(pyproject_path: Path) -> dict[str, str]:
    if not pyproject_path.exists():
        return {"name": "unknown", "version": "unknown"}
    try:
        with pyproject_path.open("rb") as f:
            obj = tomllib.load(f)
    except Exception:
        return {"name": "unknown", "version": "unknown"}
    if not isinstance(obj, dict):
        return {"name": "unknown", "version": "unknown"}
    proj = obj.get("project") if isinstance(obj.get("project"), dict) else {}
    name = proj.get("name") if isinstance(proj.get("name"), str) and proj.get("name") else "unknown"
    version = proj.get("version") if isinstance(proj.get("version"), str) and proj.get("version") else "unknown"
    return {"name": name, "version": version}


def main() -> None:
    root = repo_root()
    out_dir = root / "supply_chain"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "sbom.v1.json"

    created_at = iso_utc_now()
    py_ver = platform.python_version()

    requirements_path = root / "requirements-dev.txt"
    jsonschema_ver = read_pinned_version(requirements_path, "jsonschema")
    if jsonschema_ver is None:
        try:
            jsonschema_ver = pkg_version("jsonschema")
        except PackageNotFoundError:
            jsonschema_ver = "unknown"
        except Exception:
            jsonschema_ver = "unknown"

    commit = try_git_head(root)

    project = read_project_from_pyproject(root / "pyproject.toml")

    components: list[dict[str, Any]] = [
        {"name": "python", "type": "runtime", "version": py_ver},
        {"name": "jsonschema", "type": "library", "version": jsonschema_ver},
        {"name": "repo", "type": "source", "version": commit},
    ]
    components.sort(key=lambda c: str(c.get("name", "")))

    sbom = {
        "version": "v1",
        "created_at": created_at,
        "project": project,
        "components": components,
    }

    out_path.write_text(json.dumps(sbom, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "OK", "sbom_path": str(out_path)}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())

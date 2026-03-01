from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path


def run_cli_contract_checks(repo_root: Path) -> None:
    proc_cli_import = subprocess.run(
        [sys.executable, "-c", "from src.cli import main; print('CLI_OK')"],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if proc_cli_import.returncode != 0 or "CLI_OK" not in (proc_cli_import.stdout or ""):
        raise SystemExit(
            "Smoke test failed: CLI module import check failed.\n"
            + (proc_cli_import.stderr or proc_cli_import.stdout or "")
        )

    proc_examples_import = subprocess.run(
        [
            sys.executable,
            "-c",
            "import examples.sdk_run_demo; import examples.policy_check_demo; print('EXAMPLES_IMPORT_OK')",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if proc_examples_import.returncode != 0 or "EXAMPLES_IMPORT_OK" not in (proc_examples_import.stdout or ""):
        raise SystemExit(
            "Smoke test failed: examples import check failed.\n"
            + (proc_examples_import.stderr or proc_examples_import.stdout or "")
        )

    proc_cli_help = subprocess.run(
        [sys.executable, "-m", "src.cli", "--help"],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if proc_cli_help.returncode != 0:
        raise SystemExit(
            "Smoke test failed: src.cli --help must exit 0.\n"
            + (proc_cli_help.stderr or proc_cli_help.stdout or "")
        )
    cli_help_text = (proc_cli_help.stdout or "") + (proc_cli_help.stderr or "")
    required_help_terms = [
        "run",
        "ops",
        "sdk-demo",
        "urn:core:docs:policy_review",
        "urn:core:ops:dlq_triage",
    ]
    missing_help_terms = [t for t in required_help_terms if t not in cli_help_text]
    if missing_help_terms:
        raise SystemExit(
            "Smoke test failed: src.cli --help missing terms: "
            + ", ".join(missing_help_terms)
        )

    proc_cli_run_help = subprocess.run(
        [sys.executable, "-m", "src.cli", "run", "--help"],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if proc_cli_run_help.returncode != 0:
        raise SystemExit(
            "Smoke test failed: src.cli run --help must exit 0.\n"
            + (proc_cli_run_help.stderr or proc_cli_run_help.stdout or "")
        )
    cli_run_help_text = (proc_cli_run_help.stdout or "") + (proc_cli_run_help.stderr or "")
    required_run_help_terms = [
        "--side-effect-policy",
        "merge/deploy",
        "blocked",
    ]
    missing_run_terms = [t for t in required_run_help_terms if t not in cli_run_help_text]
    if missing_run_terms:
        raise SystemExit(
            "Smoke test failed: src.cli run --help missing terms: "
            + ", ".join(missing_run_terms)
        )

    pyproject_path = repo_root / "pyproject.toml"
    if not pyproject_path.exists():
        raise SystemExit("Smoke test failed: missing pyproject.toml for CLI version check.")
    with pyproject_path.open("rb") as handle:
        py_obj = tomllib.load(handle)
    project = py_obj.get("project") if isinstance(py_obj, dict) else None
    if not isinstance(project, dict) or not isinstance(project.get("version"), str):
        raise SystemExit("Smoke test failed: pyproject.toml missing [project].version for CLI version check.")
    expected_version = project["version"].strip()

    proc_cli_version = subprocess.run(
        [sys.executable, "-m", "src.cli", "--version"],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if proc_cli_version.returncode != 0:
        raise SystemExit(
            "Smoke test failed: src.cli --version must exit 0.\n"
            + (proc_cli_version.stderr or proc_cli_version.stdout or "")
        )
    cli_version = (proc_cli_version.stdout or "").strip()
    if cli_version != expected_version:
        raise SystemExit(
            "Smoke test failed: src.cli --version mismatch; expected "
            + expected_version
            + " got "
            + cli_version
        )

    print("CRITICAL_CLI_HELP: ok=true")
    print(f"CRITICAL_CLI_VERSION: version={cli_version}")

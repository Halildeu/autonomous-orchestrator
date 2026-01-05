"""Contract test for dotenv loader (program-led, deterministic)."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from src.prj_kernel_api.dotenv_loader import load_env_presence, resolve_env_presence


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp_repo_root:
        repo_root = Path(tmp_repo_root)
        (repo_root / ".git").mkdir(parents=True, exist_ok=True)
        (repo_root / "AGENTS.md").write_text("router", encoding="utf-8")
        (repo_root / ".env").write_text(
            "export DEEPSEEK_API_KEY=dummy\nGOOGLE_API_KEY=dummy\n",
            encoding="utf-8",
        )

        with tempfile.TemporaryDirectory() as tmp_ws_root:
            ws = Path(tmp_ws_root)
            presence = load_env_presence(
                str(ws),
                expected_keys=["DEEPSEEK_API_KEY", "GOOGLE_API_KEY"],
                repo_root=repo_root,
                env_mode="dotenv",
            )
            if presence.get("source_used") != "repo_env":
                raise SystemExit("Dotenv test failed: expected repo_env source.")
            present_keys = presence.get("present_keys")
            if not isinstance(present_keys, set) or not {"DEEPSEEK_API_KEY", "GOOGLE_API_KEY"}.issubset(present_keys):
                raise SystemExit("Dotenv test failed: repo keys not present.")

            deepseek_present, deepseek_source = resolve_env_presence(
                "DEEPSEEK_API_KEY",
                str(ws),
                repo_root=repo_root,
                env_mode="dotenv",
            )
            if not deepseek_present or deepseek_source != "repo_env":
                raise SystemExit("Dotenv test failed: repo_env precedence missing.")

            ws_env = ws / ".env"
            ws_env.write_text("OPENAI_API_KEY=workspace\n", encoding="utf-8")

            presence = load_env_presence(
                str(ws),
                expected_keys=["OPENAI_API_KEY", "GOOGLE_API_KEY"],
                repo_root=repo_root,
                env_mode="dotenv",
            )
            if presence.get("source_used") != "workspace_env":
                raise SystemExit("Dotenv test failed: workspace_env should win.")

            openai_present, openai_source = resolve_env_presence(
                "OPENAI_API_KEY",
                str(ws),
                repo_root=repo_root,
                env_mode="dotenv",
            )
            if not openai_present or openai_source != "workspace_env":
                raise SystemExit("Dotenv test failed: workspace override missing.")

            google_present, google_source = resolve_env_presence(
                "GOOGLE_API_KEY",
                str(ws),
                repo_root=repo_root,
                env_mode="dotenv",
            )
            if not google_present or google_source != "repo_env":
                raise SystemExit("Dotenv test failed: repo fallback missing.")

    print(json.dumps({"status": "OK", "workspace": "temp"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

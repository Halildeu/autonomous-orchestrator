from __future__ import annotations

import os


def token_present(token_env: str) -> bool:
    return bool(os.environ.get(str(token_env or "").strip(), "").strip())


def gh_subprocess_env(token_env: str = "") -> dict[str, str]:
    """Return a subprocess env that lets gh use the operator-selected token env.

    The token value is copied only into the child process environment. Callers
    must never include this env or token value in reports.
    """
    env = os.environ.copy()
    token_name = str(token_env or "").strip()
    token_value = env.get(token_name, "").strip() if token_name else ""
    if token_value:
        env["GH_TOKEN"] = token_value
    return env

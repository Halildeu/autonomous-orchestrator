# Repo-local Codex config

This folder contains the SSOT Codex config **template** for this repo. It is
deterministic and contains no secrets.

## How it works

Codex reads `.codex/config.toml` from the project root alongside the global
`~/.codex/config.toml` (project must be marked trusted — see below).
Credentials are resolved from the default global store (keyring or file-backed
fallback at `~/.codex/auth.json`); they must NOT be duplicated here.

### Interactive CLI (user-mode)

**Do NOT manually export `CODEX_HOME` to this directory.** Doing so redirects
credential lookup here (where no auth exists) and causes 401 errors. Leave
`CODEX_HOME` unset; Codex merges repo-local config automatically.

### Program-led runners (internal)

Orchestrator bootstrap (`src/prj_kernel_api/codex_home.py`) generates an
effective config at `<WS>/.cache/codex_home/config.toml` by merging this
template with the managed overlay (`policies/policy_codex_runtime.v1.json`).
Runners may set `CODEX_HOME` to that workspace path internally — this is the
only sanctioned `CODEX_HOME` override.

## Important notes

- **Template ≠ effective runtime.** This file contains `model = gpt-5.2-codex`;
  the managed overlay upgrades it to `gpt-5.3-codex`. Auto-read of this template
  alone does NOT apply the overlay — only the orchestrator bootstrap does.
- **Trust requirement.** If repo-local config is not being loaded, mark the
  project as trusted in `~/.codex/config.toml`:
  ```toml
  [projects."/Users/<you>/Documents/autonomous-orchestrator"]
  trust_level = "trusted"
  ```
- See `CODEX-CONFIG-CONTRACT.v1.md` for the full effective runtime spec.

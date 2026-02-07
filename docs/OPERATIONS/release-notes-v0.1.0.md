# v0.1.0 Release Notes

Release date: **2025-12-31**

## Highlights

From `CHANGELOG.md`:

- Initial public skeleton: control plane, evidence, gates, ops CLI, SDK, packaging

## Install & Quick Start (copy-paste)

From repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt

# Full end-to-end sanity
python smoke_test.py

# SDK demos (no secrets / no network required)
python examples/sdk_run_demo.py
python examples/policy_check_demo.py
```

## Optional: Integration Check (real OpenAI call)

The repo includes an integration-only ping command. By default, policy blocks network access (deterministic + safe).

```bash
python -m src.ops.manage openai-ping
```

If you want this to succeed locally:
- Set `policies/policy_security.v1.json`:
  - `network_access=true`
  - `network_allowlist=["api.openai.com"]`
- Provide `OPENAI_API_KEY` via environment (or `.env`, which is git-ignored).


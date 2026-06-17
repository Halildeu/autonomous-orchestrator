# Board Live Setup Evidence (v1)

Status: REVIEW_READY  
Scope: BOG-6B/BOG-6C GitHub ProjectV2 setup dry-run, gated apply, and live acceptance  
Generated: 2026-06-17  
Mode: dry-run by default; live mutation requires explicit `APPLY_BOARD_GOVERNANCE_BOG_6B` confirmation plus token boundary and accepted dry-run digest

## 1. Purpose

BOG-6B turns the BOG-6A finding into an operator-bound setup path.

BOG-6A proved:

- the `Halildeu` account can read the repo and ProjectV2 owner inventory,
- the target `autonomous-orchestrator Governance Board` does not exist,
- existing `platform Roadmap` field options do not match this repo contract.

BOG-6B adds a program-led setup command that can plan the missing board and,
only with explicit confirmation, create a narrow ProjectV2 and required fields.

## 2. Implemented Command

Command:

```bash
python3 -m src.ops.manage board-setup
```

Supported modes:

- `report`
- `dry-run`
- `apply`

Apply gate:

- confirmation string: `APPLY_BOARD_GOVERNANCE_BOG_6B`
- token env must be present,
- custom `--token-env` is bridged to child-process `GH_TOKEN`,
- accepted dry-run digest must be supplied with `--accepted-digest`,
- `gh` must be available,
- target owner/repo must be readable,
- existing field option mismatch blocks instead of silently editing options.

Allowed mutation commands in apply mode:

- `gh project create`
- `gh project field-create`
- `gh project link`
- `gh api graphql` only for `updateProjectV2Field` single-select option
  reconciliation on a newly created board

Forbidden by design:

- issue creation,
- issue edit,
- issue close,
- ProjectV2 item edit,
- `Done` automation,
- silent field-option migration on an existing board.
- issue/PR mutation during setup.

## 3. Local Contract Evidence

Implemented files:

- `src/ops/board/setup.py`
- `src/ops/commands/board_cmds.py`
- `tests/contract/test_board_setup.py`

Contract test:

```text
python3 -m pytest tests/contract/test_board_setup.py -q
8 passed
```

Tested behavior:

- missing target board dry-run plans `create_project`,
  `reconcile_required_fields_after_create`, and optional repo link,
- `apply` without confirmation blocks before any `gh` call,
- `apply` without token env blocks before any `gh` call,
- `apply` without accepted dry-run digest blocks before any `gh` call,
- accepted digest mismatch blocks before mutation after read-only recomputation,
- custom token env is available to fake `gh` as `GH_TOKEN`,
- token values are not present in command reports,
- fake live apply creates project and required fields through fake `gh`,
- newly created default `Status` missing-options are completed with bounded
  `updateProjectV2Field`,
- existing field option mismatch blocks before mutation,
- fake `gh` call ledger contains no issue commands and no ProjectV2 item edit.

Full board regression:

```text
python3 -m pytest tests/contract/test_board_commands.py tests/contract/test_board_apply.py tests/contract/test_board_projection.py tests/contract/test_board_pr_merge.py tests/contract/test_board_sync.py tests/contract/test_board_live_probe.py tests/contract/test_board_setup.py tests/contract/test_board_auth_preflight.py -q
48 passed
```

Core and governance gates:

```text
CORE_UNLOCK=1 CORE_UNLOCK_REASON='BOG-6B board live setup dry-run and gated apply implementation' python3 ci/core_ops_contract_test.py
{"status": "OK", "tests_passed": 10, "tests_failed": 0}

python3 ci/validate_schemas.py
OK

python3 -m src.ops.manage policy-check --source both
{"status": "OK", ...}

python3 -m src.ops.manage doc-nav-check --workspace-root .cache/ws_customer_default
{"status": "OK", ...}
```

## 4. Live Dry-Run Evidence

Live command:

```text
python3 -m src.ops.manage board-setup --repo Halildeu/autonomous-orchestrator --project-owner Halildeu --mode dry-run --link-repo
```

Report:

- `.cache/ws_customer_default/.cache/reports/board_setup.v1.json`

Observed live result:

- Status: `OK`
- Repo permission: `ADMIN`
- Target board title: `autonomous-orchestrator Governance Board`
- Resolved project: none
- Planned actions:
  - `create_project`
  - `reconcile_required_fields_after_create`
  - `link_project_repo_after_create`
- Mutation commands: none

This proves the live mutation plan was known and bounded before BOG-6C apply.
The later BOG-6C apply evidence below records the actual mutation ledger.

## 5. Apply Preflight Hardening

Live apply preflight without confirmation:

```text
python3 -m src.ops.manage board-setup --repo Halildeu/autonomous-orchestrator --project-owner Halildeu --mode apply --link-repo --out .cache/reports/board_setup_apply_preflight_missing_confirm.v1.json
```

Observed result:

- Status: `BLOCKED`
- Blocked reasons: `APPLY_CONFIRMATION_REQUIRED`,
  `TOKEN_ENV_MISSING:GITHUB_TOKEN`
- `read_only_commands`: empty
- `mutation_commands`: empty

Live apply preflight with confirmation but missing token env:

```text
python3 -m src.ops.manage board-setup --repo Halildeu/autonomous-orchestrator --project-owner Halildeu --mode apply --apply-confirm APPLY_BOARD_GOVERNANCE_BOG_6B --token-env BOG6C_TOKEN_MISSING --link-repo --out .cache/reports/board_setup_apply_preflight_missing_token.v1.json
```

Observed result:

- Status: `BLOCKED`
- Blocked reason: `TOKEN_ENV_MISSING:BOG6C_TOKEN_MISSING`
- `read_only_commands`: empty
- `mutation_commands`: empty

This hardening matters because apply mode now fails before `gh auth status`,
repo reads, keyring access, or network calls when operator confirmation/token
boundary is missing.

## 6. Accepted Digest Gate

Setup dry-run now emits `setup_digest`. The digest covers repo, board title,
project owner, resolved ProjectV2 identity if any, planned setup actions, and
repo link intent.

Apply mode requires the operator to pass that digest back with
`--accepted-digest`.

Gate behavior:

- Missing `--accepted-digest` blocks before any `gh` call.
- Mismatched digest blocks before mutation after read-only recomputation.
- Matching digest permits mutation only if confirmation and token env are also
  present.

Live missing-digest preflight:

```text
python3 -m src.ops.manage board-setup --repo Halildeu/autonomous-orchestrator --project-owner Halildeu --mode apply --apply-confirm APPLY_BOARD_GOVERNANCE_BOG_6B --token-env BOG6C_TOKEN_MISSING --link-repo --out .cache/reports/board_setup_apply_preflight_missing_digest.v1.json
```

Observed result:

- Status: `BLOCKED`
- Blocked reasons: `TOKEN_ENV_MISSING:BOG6C_TOKEN_MISSING`,
  `ACCEPTED_DIGEST_REQUIRED`
- `read_only_commands`: empty
- `mutation_commands`: empty

## 7. Live Apply Evidence

Latest accepted dry-run digest:

```text
e4a3d24540cb5725d5bc1e33bc7a004e0945159532cdab51127214bbd3dcc7ea
```

Live apply command was run with an ephemeral token env derived from the
authenticated `gh` session. The token value was not printed and was not written
to any JSON report.

Report:

- `.cache/reports/board_setup_apply_live.v1.json`

Observed result:

- Status: `OK`
- Created ProjectV2: `#5`
- Project ID: `PVT_kwHOCx7tY84Ba38C`
- URL: `https://github.com/users/Halildeu/projects/5`
- Applied actions:
  - `create_project`
  - `update_project_field_options` for `Status`
  - `create_project_field` for `Faz`
  - `create_project_field` for `Track`
  - `create_project_field` for `Priority`
  - `create_project_field` for `Kind`
  - `link_project_repo`
- Mutation commands:
  - `project create`
  - `api graphql:updateProjectV2Field`
  - `project field-create`
  - `project link`

Live post-apply probe:

- `.cache/reports/board_live_probe_project5.v1.json`
- Status: `OK`
- Field compatibility: `OK`
- Missing fields: none
- Missing options: none
- Item count: `0`

## 8. Token Env Bridge

BOG-6C token-boundary hardening adds a shared helper:

- `src/ops/board/gh_env.py`

Behavior:

- `--token-env <NAME>` records only the env variable name.
- If `<NAME>` is present, the value is copied only into the child process as
  `GH_TOKEN`.
- The token value is not written to JSON reports, command ledgers, or evidence.
- The bridge is used by setup apply, live probe reads, board apply, and board
  sync.

Contract evidence:

- `tests/contract/test_board_setup.py`
- `tests/contract/test_board_live_probe.py`
- `tests/contract/test_board_apply.py`
- `tests/contract/test_board_sync.py`

The fake `gh` harness requires `GH_TOKEN` when `REQUIRE_GH_TOKEN=1`, and tests
assert the synthetic token value is absent from returned reports.

Focused token bridge regression:

```text
python3 -m pytest tests/contract/test_board_apply.py tests/contract/test_board_sync.py tests/contract/test_board_setup.py tests/contract/test_board_live_probe.py -q
22 passed
```

## 9. Auth Preflight

BOG-6C adds:

```bash
python3 -m src.ops.manage board-auth-preflight
```

Default behavior:

- report-only,
- no mutation,
- if `--token-env` is missing, it blocks before any `gh` call,
- keyring auth is not attempted unless `--allow-keyring-auth` is explicitly set,
- explicit keyring probing is bounded by `--gh-timeout-seconds`.

Live current result:

```text
python3 -m src.ops.manage board-auth-preflight --out .cache/reports/board_auth_preflight.v1.json
```

Observed:

- Status: `BLOCKED`
- `TOKEN_ENV_MISSING:GITHUB_TOKEN`
- `KEYRING_AUTH_NOT_ATTEMPTED`
- `read_only_commands`: empty
- `gh_available`: true

Explicit keyring probe:

```text
python3 -m src.ops.manage board-auth-preflight --allow-keyring-auth --gh-timeout-seconds 10 --out .cache/reports/board_auth_preflight_keyring.v1.json
```

Observed:

- Status: `OK`
- Account: `Halildeu`
- Required scopes present: `project`, `repo`
- Token value not recorded.

Contract evidence:

```text
python3 -m pytest tests/contract/test_board_auth_preflight.py -q
5 passed
```

## 10. Acceptance Boundary

BOG-6B/BOG-6C is `REVIEW_READY` because:

- setup command exists,
- dry-run path is live and report-backed,
- fake apply path is tested,
- live apply created the narrow governance ProjectV2 `#5`,
- required field families and options are live-compatible,
- the repo was linked to the ProjectV2,
- confirmation/token gates are tested,
- missing confirmation/token fail before any `gh` call,
- missing digest fails before any `gh` call,
- digest mismatch fails before mutation,
- custom token env bridges to child `GH_TOKEN` without leaking the token value,
- auth preflight reports missing token env without keyring access,
- explicit keyring auth probing is timeout-bounded,
- existing-board option mismatch remains fail-closed,
- setup mutation ledger is recorded.

BOG-6B/BOG-6C does not prove:

- projection/sync apply has run on the real board,
- issues have been created or added to the board,
- ProjectV2 item fields have been synced,
- user-path or runtime acceptance is complete.

## 11. Next Gate

BOG-7 completed the first live governed issue/item seed after this setup gate.
The next safe gate is live projection generation and sync validation:

1. Read issue `#78` and ProjectV2 `#5` item inventory as live input.
2. Produce a live metadata map for field IDs, option IDs, and item IDs.
3. Generate a fresh `board-projection` dry-run from live-compatible data.
4. Accept the projection digest before any `board-sync --mode apply`.
5. Keep additional issue creation, issue close, `Done`, and ProjectV2 item movement behind
   their own explicit gates.

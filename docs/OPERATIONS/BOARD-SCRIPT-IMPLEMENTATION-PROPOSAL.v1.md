# Board Script Implementation Proposal (v1)

Status: SUPERSEDED_BY_IMPLEMENTATION_EVIDENCE  
Started: 2026-06-17  
Scope: BOG-3B dry-run/report-only board command implementation proposal  
Current mode: historical proposal; implementation evidence now exists in `docs/OPERATIONS/BOARD-SCRIPT-IMPLEMENTATION-EVIDENCE.v1.md`

Superseded by:

```text
docs/OPERATIONS/BOARD-SCRIPT-IMPLEMENTATION-EVIDENCE.v1.md
```

The original blocker is retained below as historical evidence. BOG-3B was later
implemented under a narrow one-shot source window and remains `REVIEW_READY`,
not live-apply ready.

## 1. Purpose

BOG-3B requires actual source and test files for the minimal board command
implementation. The current repository guardrail blocks `src/**` writes unless
an explicit source-write boundary is active.

This proposal records the intended implementation scope so the next authorized
implementation step can proceed without broad or fake work.

## 2. Current Guardrail Evidence

Command checked:

```text
python3 -m src.ops.manage write-authorize --workspace-root .cache/ws_customer_default --target-path src/ops/commands/board_cmds.py
```

Observed result:

```json
{
  "status": "BLOCKED",
  "target_path": "src/ops/commands/board_cmds.py",
  "core_lock": "ON",
  "core_unlock_required": true,
  "core_unlock_active": false,
  "deny_reasons": [
    "CORE_UNLOCK=1 required for src/ writes"
  ],
  "required_validations": [
    "python3 ci/core_ops_contract_test.py"
  ]
}
```

Because source writes are blocked, BOG-3B must not be claimed complete yet.

## 3. Intended Source Files

Implementation should be limited to these files unless a later review expands
the scope:

```text
src/ops/board/__init__.py
src/ops/board/models.py
src/ops/board/rules.py
src/ops/board/reports.py
src/ops/board/fixtures.py
src/ops/commands/board_cmds.py
src/ops/manage.py
tests/contract/test_board_commands.py
fixtures/board/board_list_happy.v1.json
fixtures/board/board_claim_conflict.v1.json
fixtures/board/board_needs_verify_drift.v1.json
fixtures/board/board_malformed_gh_json.v1.json
```

No `.github/ISSUE_TEMPLATE`, `.github/PULL_REQUEST_TEMPLATE`, GitHub workflow,
live GitHub Project, issue, PR, label, or runtime file is part of BOG-3B.

## 4. Intended Commands

BOG-3B should register these report/dry-run commands through `src.ops.manage`:

```text
board-list
board-claim
board-heartbeat
board-release
board-verify
board-backlog-add
```

All commands must accept:

```text
--workspace-root
--repo
--board-title
--mode report|dry-run|apply
--out
--fixture
```

`--mode apply` must return `BLOCKED` until BOG-3C explicitly authorizes live
apply semantics.

## 5. Implementation Requirements

BOG-3B implementation must satisfy:

- default mode is `report`,
- fixture-backed `dry-run` works without network,
- no live GitHub writes,
- `applied_actions` is empty in `report` and `dry-run`,
- every output contains non-empty `evidence.does_not_prove`,
- malformed fixture JSON returns `ERROR` or `BLOCKED`, not a traceback,
- missing token/auth-like fixture returns `BLOCKED`,
- competing active claim returns `BLOCKED`,
- `Kind=umbrella` claim attempt returns `BLOCKED`,
- `Needs Verify` without `needs-verification` is reported as drift,
- forbidden close keywords are reported as drift,
- no command plans or applies `Done` for runtime/governance work.

## 6. Test Requirements

Required tests:

```text
python3 -m pytest tests/contract/test_board_commands.py
python3 ci/core_ops_contract_test.py
```

Test assertions must prove:

- all six commands are registered in `src.ops.manage`,
- each command emits parseable JSON,
- fixture-backed commands do not require network,
- `apply` is blocked,
- no output in report/dry-run contains applied actions,
- drift findings are deterministic,
- malformed fixture input does not leak stack traces or secrets.

## 7. Source-Write Boundary Required

Before BOG-3B implementation can proceed, an operator-approved source-write
boundary is required.

Acceptable boundary evidence must include one of:

- active repo policy/env allowing `src/**` writes for these exact paths, or
- an explicit one-shot source window naming the allowed paths and TTL, or
- a reviewed policy change that moves the board command implementation paths
  into the approved allowlist.

The implementation must stop if the allowed path list is broader than needed or
if the TTL/approval reason is missing.

## 8. BOG-3B Acceptance

BOG-3B is `REVIEW_READY` only when:

- source-write boundary evidence exists,
- intended files are implemented,
- all six commands are registered,
- fixture-backed tests pass,
- `apply` remains blocked,
- schema/policy/doc-nav checks pass,
- `ci/core_ops_contract_test.py` passes,
- no live GitHub write occurred,
- adoption plan records BOG-3B as implemented.

Until then, BOG-3B status is `BLOCKED`, not `DONE`.

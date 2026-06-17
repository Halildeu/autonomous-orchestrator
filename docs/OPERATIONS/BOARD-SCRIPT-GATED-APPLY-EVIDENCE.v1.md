# Board Script Gated Apply Evidence (v1)

Status: REVIEW_READY  
Started: 2026-06-17  
Scope: BOG-3C explicit-confirm gated board apply implementation evidence  
Current mode: source implementation completed under one-shot source window;
live GitHub writes are possible only when apply confirmation, token env, repo,
`gh` binary, and supported action metadata are all present

## 1. Summary

BOG-3C implemented a gated apply executor for board governance commands.

Implemented apply gate:

```text
--mode apply
--apply-confirm APPLY_BOARD_GOVERNANCE_BOG_3C
--token-env <TOKEN_ENV_NAME>
--gh-bin <gh-or-fake-gh-path>
```

The implementation does not enable automatic issue close, does not automate
`Done`, and does not apply unsupported actions. Blocked paths fail before any
`gh` subprocess call.

## 2. Source Window Evidence

Workspace override path:

```text
.cache/ws_customer_default/.cache/policy_overrides/policy_core_immutability.override.v1.json
```

Window metadata:

```text
enabled=true during implementation
opened_at=2026-06-17T00:39:18Z
ttl_seconds=3600
reason=BOG-3C board governance gated apply implementation
```

Allowed source/test/fixture paths:

```text
src/ops/board/apply.py
src/ops/board/rules.py
src/ops/commands/board_cmds.py
tests/contract/test_board_apply.py
fixtures/board/board_apply_happy.v1.json
fixtures/board/board_apply_missing_token.v1.json
fixtures/board/board_apply_project_status.v1.json
```

Write authorization checks passed for source targets with:

```text
CORE_UNLOCK=1 CORE_UNLOCK_REASON='BOG-3C board governance gated apply implementation'
```

## 3. Implemented Files

Source:

```text
src/ops/board/apply.py
src/ops/board/rules.py
src/ops/commands/board_cmds.py
```

Tests and fixtures:

```text
tests/contract/test_board_apply.py
fixtures/board/board_apply_happy.v1.json
fixtures/board/board_apply_missing_token.v1.json
fixtures/board/board_apply_project_status.v1.json
```

## 4. Behavior Implemented

Implemented:

- explicit apply confirmation string;
- token env presence check without logging token values;
- `gh` binary availability check;
- fail-closed preflight before mutation;
- fake-`gh` contract tests;
- supported `append_comment` action via `gh issue comment`;
- supported `set_board_status` action via `gh project item-edit`;
- supported `create_issue` action via `gh issue create`;
- blocked unsupported action behavior before any `gh` call;
- blocked `Done` automation;
- blocked missing metadata behavior.

Not implemented in BOG-3C:

- automatic issue close;
- automatic `Done` transition;
- full live GitHub inventory discovery;
- live ProjectV2 id discovery;
- live issue body `agent-state:v1` rewrite;
- workflow automation;
- runtime or browser-user-path acceptance.

## 5. Test Evidence

Contract test:

```text
python3 -m pytest tests/contract/test_board_commands.py tests/contract/test_board_apply.py tests/contract/test_board_projection.py -q
```

Observed result:

```text
18 passed in 2.32s
```

Smoke command with fake executable:

```text
BOARD_TEST_TOKEN=present python3 -m src.ops.manage board-verify \
  --mode apply \
  --apply-confirm APPLY_BOARD_GOVERNANCE_BOG_3C \
  --fixture fixtures/board/board_apply_project_status.v1.json \
  --issue 203 \
  --evidence 'manual smoke' \
  --evidence-type source \
  --gh-bin /bin/echo \
  --token-env BOARD_TEST_TOKEN \
  --out none
```

Observed result:

```text
status=OK
applied_actions[0].type=append_comment
applied_actions[1].type=set_board_status
blocked_reasons=[]
```

Blocked path evidence:

```text
missing confirmation => status=BLOCKED, no fake-gh call
missing token env => status=BLOCKED, no fake-gh call
unsupported update_agent_state action => status=BLOCKED, no fake-gh call
```

## 6. Does Not Prove

This implementation evidence does not prove:

- live GitHub token scope is sufficient;
- live ProjectV2 IDs are discoverable;
- live issue body rewrite is implemented;
- runtime or user-path acceptance;
- BOG-4B workflow behavior;
- BOG-5C operator-bound sync apply readiness.

## 7. BOG-3C Acceptance State

BOG-3C is `REVIEW_READY`.

The gated apply executor exists and is tested. It is not `DONE` until accepted.
Live use still requires explicit confirmation and a token env at runtime.

# Board PR Merge Evidence Workflow Implementation Evidence (v1)

Status: REVIEW_READY  
Started: 2026-06-17  
Scope: BOG-4B PR merge evidence workflow implementation evidence  
Current mode: workflow and parser implemented; live mutation remains gated by
BOG-3C apply confirmation and token env

## 1. Summary

BOG-4B implemented the PR merge evidence path.

Implemented surfaces:

```text
.github/workflows/board-pr-merge-evidence.yml
python3 -m src.ops.manage board-pr-merge
```

The workflow triggers on `pull_request.closed`, ignores unmerged PRs, avoids
`pull_request_target`, parses `Tracked by #N`, and calls the program-led ops
entrypoint. It does not close issues and does not mark work `Done`.

## 2. Source And Workflow Window Evidence

Workspace override path:

```text
.cache/ws_customer_default/.cache/policy_overrides/policy_core_immutability.override.v1.json
```

Window metadata:

```text
enabled=true during implementation
opened_at=2026-06-17T00:48:06Z
ttl_seconds=3600
reason=BOG-4B board PR merge evidence workflow implementation
```

Allowed paths:

```text
src/ops/board/pr_merge.py
src/ops/commands/board_cmds.py
.github/workflows/board-pr-merge-evidence.yml
tests/contract/test_board_pr_merge.py
fixtures/board/pr_merge_event_merged.v1.json
fixtures/board/pr_merge_event_unmerged.v1.json
fixtures/board/pr_merge_event_no_tracked.v1.json
fixtures/board/pr_merge_event_forbidden_close.v1.json
fixtures/board/pr_merge_issues_happy.v1.json
fixtures/board/pr_merge_issues_existing_marker.v1.json
```

Write authorization passed for:

```text
src/ops/board/pr_merge.py
src/ops/commands/board_cmds.py
.github/workflows/board-pr-merge-evidence.yml
```

## 3. Behavior Implemented

Implemented:

- `pull_request.closed` workflow trigger;
- merged-only processing condition;
- `Tracked by #N` parser;
- duplicate issue de-duplication;
- forbidden close-keyword finding;
- idempotent evidence marker;
- fake-`gh` apply tests;
- missing-token report-only fallback;
- existing-marker no-duplicate-comment behavior;
- `needs-verification` label action;
- ProjectV2 `Needs Verify` status action when explicit item/field metadata is
  present;
- no issue close;
- no `Done` automation.

Not implemented in BOG-4B:

- live ProjectV2 item discovery;
- live issue body `agent-state:v1` rewrite;
- full live eligibility inventory when no issue metadata fixture or future live
  metadata adapter is provided;
- runtime or browser-user-path acceptance.

## 4. Test Evidence

Contract test:

```text
python3 -m pytest tests/contract/test_board_commands.py tests/contract/test_board_apply.py tests/contract/test_board_projection.py tests/contract/test_board_pr_merge.py -q
```

Observed result:

```text
24 passed in 3.53s
```

Smoke command with fake executable:

```text
BOARD_TEST_TOKEN=present python3 -m src.ops.manage board-pr-merge \
  --event fixtures/board/pr_merge_event_merged.v1.json \
  --issue-fixture fixtures/board/pr_merge_issues_happy.v1.json \
  --mode apply \
  --apply-confirm APPLY_BOARD_GOVERNANCE_BOG_3C \
  --token-env BOARD_TEST_TOKEN \
  --gh-bin /bin/echo \
  --out none
```

Observed result:

```text
status=OK
applied_actions includes append_evidence_comment, add_label, set_board_status
blocked_reasons=[]
```

Blocked/fallback evidence:

```text
closed but unmerged PR => no action
merged PR without Tracked by => no action
missing token => status=WARN, no fake-gh call
forbidden close keyword => status=BLOCKED, no fake-gh call
existing evidence marker => no duplicate comment
```

## 5. Does Not Prove

This implementation evidence does not prove:

- live GitHub token scope is sufficient;
- live ProjectV2 item discovery works;
- live issue metadata discovery is complete;
- runtime/live acceptance is complete;
- user-path acceptance is complete;
- issue is ready to close;
- BOG-5C operator-bound sync apply readiness.

## 6. BOG-4B Acceptance State

BOG-4B is `REVIEW_READY`.

The workflow and parser are implemented and tested. It is not `DONE` until
accepted. Live ProjectV2 status movement requires explicit metadata or a future
live discovery adapter.

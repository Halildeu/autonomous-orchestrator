# Board Canonical Router and Review Packaging Evidence (v1)

Status: REVIEW_READY  
Scope: BOG-10 AGENTS router integration, customer-friendly UX routing, and
review packaging boundary  
Generated: 2026-06-17  
Mode: repo-local docs/router integration; no issue close or `Done` automation

## 1. Purpose

BOG-10 closes the repo-integration gap after live board sync validation.

Before this step, the board governance artifacts existed and live GitHub
ProjectV2 evidence was available, but the repository's AGENTS-only canonical
router did not yet name the board governance operating model, policy, projection
contract, or PR evidence workflow.

That made the work usable but not fully adopted by the repo's own navigation
contract.

## 2. Router Changes

Implemented router changes:

- `AGENTS.md` now lists the board governance canonical docs and contracts in
  the SSOT entrypoint map.
- `AGENTS.md` now includes `.github/workflows/board-pr-merge-evidence.yml` in
  the core write allowlist wording.
- `AGENTS.md` now defines the board operating rule:
  - board is not repo SSOT;
  - `project-roadmap` gates board ingestion;
  - `Tracked by #N` is the default PR relation;
  - `Needs Verify` is an acceptance queue;
  - `Done` and issue close require separate acceptance evidence.
- `AGENTS.md` now defines the safe live sync order:
  `board-projection-live` -> `board-metadata-live` ->
  `board-sync --mode dry-run`; apply remains digest/target/confirmation/token
  gated.

## 3. Customer-Friendly UX Changes

`docs/OPERATIONS/CODEX-UX.md` now maps natural-language board requests to
operator-run commands:

- `Board durumunu göster`
- `Board doğrulamasını ilerlet`

The user still does not run shell commands. The agent runs bounded ops commands
and reports in AUTOPILOT CHAT format.

## 4. Review Packaging Boundary

BOG-10 does not claim canonical maturity increase on `main`.

Per AGENTS maturity rules:

- branch-local implementation can be REVIEW_READY;
- canonical maturity increases only after PR merge and CI gate pass;
- issue `#78` remains open in `Needs Verify`;
- `Done` and issue close remain out of scope until project-owner acceptance.

## 5. Write Boundary Evidence

Pre-edit authorization checks:

```text
python3 -m src.ops.manage write-authorize --workspace-root .cache/ws_customer_default --target-path AGENTS.md
status=PASS

python3 -m src.ops.manage write-authorize --workspace-root .cache/ws_customer_default --target-path .github/workflows/board-pr-merge-evidence.yml
status=PASS
```

The checks showed both paths were eligible under the current repo policy. No
secret or token value was printed.

## 6. Gate Evidence

Post-router checks:

```text
python3 -m src.ops.manage doc-nav-check --workspace-root .cache/ws_customer_default
status=OK

python3 -m src.ops.manage policy-check --source both
status=OK

python3 ci/validate_schemas.py
OK: 209 schema files validated.

python3 -m pytest tests/contract/test_board_setup.py tests/contract/test_board_sync.py tests/contract/test_board_apply.py tests/contract/test_board_live_probe.py tests/contract/test_board_metadata.py tests/contract/test_board_live_projection.py tests/contract/test_board_auth_preflight.py tests/contract/test_board_pr_merge.py tests/contract/test_board_commands.py tests/contract/test_board_projection.py tests/contract/test_board_seed.py -q
58 passed

CORE_UNLOCK=1 CORE_UNLOCK_REASON='BOG-10 canonical board governance router integration' python3 ci/core_ops_contract_test.py
{"status": "OK", "tests_passed": 10, "tests_failed": 0}

git diff --check
OK
```

Live board no-op verification:

```text
python3 -m src.ops.manage board-projection-live --repo Halildeu/autonomous-orchestrator --project-owner Halildeu --project-number 5 --mode dry-run --out .cache/reports/board_projection_live_project5.v1.json
status=OK
projection_digest=417b90e0a78d9dc2be553182bc2384522b924523a2262750cf2a86fa15e0cb0c
drift_total=0

python3 -m src.ops.manage board-sync --projection .cache/ws_customer_default/.cache/reports/board_projection_live_project5.v1.json --metadata .cache/ws_customer_default/.cache/reports/board_metadata_live_project5.v1.json --accepted-digest 417b90e0a78d9dc2be553182bc2384522b924523a2262750cf2a86fa15e0cb0c --target-board-id PVT_kwHOCx7tY84Ba38C --mode dry-run --out .cache/reports/board_sync_live_project5_noop.v1.json
status=OK
noop=true
drift_total=0
planned_actions=[]
applied_actions=[]
```

## 7. Remaining Boundary

BOG-10 does not prove:

- PR review has happened;
- CI has run on GitHub;
- issue `#78` can be closed;
- canonical maturity has increased on `main`;
- historical backlog import is complete.

The next safe boundary is review packaging: isolate board-governance changes on
a review branch, stage only related files, and open a draft PR after local gates
remain green.

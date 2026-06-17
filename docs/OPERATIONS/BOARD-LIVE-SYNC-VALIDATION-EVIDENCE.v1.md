# Board Live Sync Validation Evidence (v1)

Status: REVIEW_READY
Scope: BOG-9 live metadata map, governed verification promotion, and no-op sync validation
Generated: 2026-06-17
Mode: read-only metadata generation plus digest-gated sync apply and final dry-run validation

## 1. Purpose

BOG-9 closes the gap between live projection and `board-sync`.

It adds a live ProjectV2 metadata map generator so `board-sync` no longer
depends on hand-written field/item ids for the target board.

It also proves the governed promotion path for the seed item: issue `#78` can
move from `Todo` to `Needs Verify` without issue closure, without `Done`, and
without broad backlog mutation.

## 2. Implemented Commands

Metadata command:

```text
python3 -m src.ops.manage board-metadata-live
```

Sync command behavior update:

- if projection already matches observed board state, `board-sync --mode dry-run`
  returns `OK` with `noop=true`;
- no mutation is emitted for an in-sync projection.

## 3. Safety Boundary

`board-metadata-live` allows only:

- `gh auth status`
- `gh project field-list`
- `gh project item-list`

It does not create, edit, close, move, or mark anything `Done`.

`board-sync` still requires accepted projection digest and explicit target board
id. When actions exist, live apply remains gated by confirmation and token env.

The live promotion in this evidence was deliberately narrow:

- issue body/label alignment for issue `#78`;
- ProjectV2 `Status` field change for item
  `PVTI_lAHOCx7tY84Ba38Czgv-mxA`;
- no issue close;
- no `Done` status;
- no historical item backfill.

## 4. Local Contract Evidence

Implemented files:

- `src/ops/board/metadata.py`
- `src/ops/board/sync.py`
- `src/ops/commands/board_cmds.py`
- `tests/contract/test_board_metadata.py`
- `tests/contract/test_board_sync.py`

Contract tests:

```text
python3 -m pytest tests/contract/test_board_metadata.py tests/contract/test_board_sync.py -q
9 passed

python3 -m pytest tests/contract/test_board_setup.py tests/contract/test_board_sync.py tests/contract/test_board_apply.py tests/contract/test_board_live_probe.py tests/contract/test_board_metadata.py tests/contract/test_board_live_projection.py tests/contract/test_board_auth_preflight.py tests/contract/test_board_pr_merge.py tests/contract/test_board_commands.py tests/contract/test_board_projection.py tests/contract/test_board_seed.py -q
58 passed
```

Tested behavior:

- live metadata command emits field and item id maps from fake `gh`;
- apply mode blocks before any `gh` call;
- `board-sync` no-op dry-run returns `OK` with `noop=true`;
- no mutation is emitted when projection and observed board already match.

Gate evidence:

```text
CORE_UNLOCK=1 CORE_UNLOCK_REASON='BOG-9 live sync validation' python3 ci/core_ops_contract_test.py
{"status": "OK", "tests_passed": 10, "tests_failed": 0}

python3 ci/validate_schemas.py
OK: 209 schema files validated.

python3 -m src.ops.manage policy-check --source both
status=OK

python3 -m src.ops.manage doc-nav-check --workspace-root .cache/ws_customer_default
status=OK
```

Post-close source write guard:

- `write-authorize` for `src/ops/board/metadata.py`,
  `src/ops/board/live_projection.py`, `src/ops/board/seed.py`,
  `src/ops/board/sync.py`, and `src/ops/commands/board_cmds.py` returned
  `BLOCKED` with `core_unlock_active=false`.

## 5. Live Metadata Evidence

Live command:

```text
python3 -m src.ops.manage board-metadata-live --repo Halildeu/autonomous-orchestrator --project-owner Halildeu --project-number 5 --project-id PVT_kwHOCx7tY84Ba38C --mode dry-run --out .cache/reports/board_metadata_live_project5.v1.json
```

Report:

- `.cache/reports/board_metadata_live_project5.v1.json`

Observed result:

- Status: `OK`
- Field count: `17`
- Item count: `1`
- Metadata digest:

```text
59bf09b1109c5cc4cf0728839366ece08d729b750f6f961ab8823c961f10e5aa
```

## 6. Live Sync Dry-Run Evidence

First live sync dry-run after issue body/label alignment:

```text
python3 -m src.ops.manage board-sync --projection .cache/ws_customer_default/.cache/reports/board_projection_live_project5.v1.json --metadata .cache/ws_customer_default/.cache/reports/board_metadata_live_project5.v1.json --accepted-digest 81626c00c971c8ee01e37a2a6bbd579a1e347fc124cf6d8448482eb086751f3f --target-board-id PVT_kwHOCx7tY84Ba38C --mode dry-run --out .cache/reports/board_sync_live_project5_needs_verify_dry_run.v1.json
```

Observed result:

- Status: `OK`
- Drift total: `1` WARN before apply
- Planned action: set ProjectV2 `Status=Needs Verify`
- Before inventory:
  - issue `#78`
  - item id `PVTI_lAHOCx7tY84Ba38Czgv-mxA`
  - `Status=Todo`
  - labels `gate`, `needs-verification`, `project-roadmap`, `quality`
- Applied actions: none

Live sync apply:

```text
GITHUB_TOKEN="$(gh auth token)" python3 -m src.ops.manage board-sync --projection .cache/ws_customer_default/.cache/reports/board_projection_live_project5.v1.json --metadata .cache/ws_customer_default/.cache/reports/board_metadata_live_project5.v1.json --accepted-digest 81626c00c971c8ee01e37a2a6bbd579a1e347fc124cf6d8448482eb086751f3f --target-board-id PVT_kwHOCx7tY84Ba38C --mode apply --apply-confirm APPLY_BOARD_GOVERNANCE_BOG_3C --out .cache/reports/board_sync_live_project5_needs_verify_apply.v1.json
```

Observed result:

- Status: `OK`
- Applied action: set ProjectV2 `Status=Needs Verify`
- Mutation ledger: one `set_project_field` entry
- Recovery note present
- No issue close or `Done` action emitted

Final live sync no-op validation:

```text
python3 -m src.ops.manage board-sync --projection .cache/ws_customer_default/.cache/reports/board_projection_live_project5.v1.json --metadata .cache/ws_customer_default/.cache/reports/board_metadata_live_project5.v1.json --accepted-digest 417b90e0a78d9dc2be553182bc2384522b924523a2262750cf2a86fa15e0cb0c --target-board-id PVT_kwHOCx7tY84Ba38C --mode dry-run --out .cache/reports/board_sync_live_project5_noop.v1.json
```

Report:

- `.cache/reports/board_sync_live_project5_noop.v1.json`
- `.cache/reports/board_sync_live_project5_needs_verify_dry_run.v1.json`
- `.cache/reports/board_sync_live_project5_needs_verify_apply.v1.json`

Observed result:

- Status: `OK`
- `noop=true`
- Drift total: `0`
- Planned actions: none
- Applied actions: none
- Mutation ledger: empty
- Before inventory contains issue `#78` and item id
  `PVTI_lAHOCx7tY84Ba38Czgv-mxA`.
- Before inventory now shows `Status=Needs Verify`.

Issue verification:

- issue `#78` remains `OPEN`;
- labels are `gate`, `needs-verification`, `project-roadmap`, and `quality`;
- ProjectV2 status is `Needs Verify`.

Append-only issue evidence comment:

- `https://github.com/Halildeu/autonomous-orchestrator/issues/78#issuecomment-4725408977`

## 7. Remaining Boundary

BOG-9 proves the live board and live projection are currently synchronized for
the seeded item at `Needs Verify`. It does not prove:

- issue `#78` should be closed;
- issue `#78` should move to `Done`;
- future roadmap items will be auto-seeded without their own accepted digest;
- browser/user-path acceptance is complete.

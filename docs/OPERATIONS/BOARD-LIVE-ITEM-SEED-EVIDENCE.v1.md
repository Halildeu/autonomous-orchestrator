# Board Live Item Seed Evidence (v1)

Status: REVIEW_READY  
Scope: BOG-7 live governed issue and ProjectV2 item seed  
Generated: 2026-06-17  
Mode: dry-run by default; live mutation requires `APPLY_BOARD_GOVERNANCE_BOG_7A`, token boundary, project id/number, and accepted seed digest

## 1. Purpose

BOG-6C created the governance ProjectV2 and proved field compatibility, but the
board had zero governed items. BOG-7 adds the first real board item without
backfilling historical completed work.

The seed item is a live gate for the remaining board population/sync acceptance
work:

```text
BOG-7: Live board item population and sync acceptance
```

## 2. Implemented Command

Command:

```text
python3 -m src.ops.manage board-seed
```

Input:

- `fixtures/board/board_seed_bog7.v1.json`

Apply gate:

- confirmation string: `APPLY_BOARD_GOVERNANCE_BOG_7A`
- accepted seed digest required
- token env required
- target ProjectV2 number required
- target ProjectV2 node id required

Allowed mutation commands:

- `gh label create`
- `gh issue create`
- `gh issue edit` only to add missing labels to an existing seed issue
- `gh project item-add`
- `gh project item-edit`

Forbidden by design:

- issue close
- PR mutation
- `Done` automation
- ProjectV2 item movement
- historical completed work backfill
- token value reporting

## 3. Seed Source

The seed source is repo-local and inspectable:

```text
fixtures/board/board_seed_bog7.v1.json
```

The seed body follows `BOARD-ISSUE-TEMPLATE-CONTRACT.v1.md` and includes:

- `agent-state:v1`
- board fields
- SSOT refs
- acceptance criteria
- evidence sections
- remaining/deferred boundary
- safety notes

## 4. Current Acceptance Boundary

BOG-7 is `REVIEW_READY` when:

- `board-seed` exists,
- dry-run emits a stable digest,
- fake-`gh` apply path passes,
- missing digest/token blocks before any `gh` call,
- no token value appears in reports,
- no issue close or `Done` action is emitted.

BOG-7 live apply acceptance requires:

- labels exist in GitHub,
- the BOG-7 issue exists,
- the issue is added to ProjectV2 `#5`,
- ProjectV2 fields are populated,
- live item inventory confirms the board is no longer empty.

The live evidence below satisfies this boundary for the first seed item. It
does not close the item or mark it complete.

## 5. Local Contract Evidence

Implemented files:

- `src/ops/board/seed.py`
- `src/ops/commands/board_cmds.py`
- `tests/contract/test_board_seed.py`
- `fixtures/board/board_seed_bog7.v1.json`

Contract tests:

```text
python3 -m pytest tests/contract/test_board_seed.py -q
4 passed

python3 -m pytest tests/contract/test_board_commands.py tests/contract/test_board_apply.py tests/contract/test_board_projection.py tests/contract/test_board_pr_merge.py tests/contract/test_board_sync.py tests/contract/test_board_live_probe.py tests/contract/test_board_setup.py tests/contract/test_board_auth_preflight.py tests/contract/test_board_seed.py -q
52 passed
```

Tested behavior:

- dry-run emits a stable `seed_digest`;
- apply requires accepted digest before any `gh` call;
- apply requires token env before any `gh` call;
- fake apply creates required labels, issue, ProjectV2 item, and field values;
- token values are not present in reports;
- issue close is not emitted;
- `Done` field value is not emitted.

## 6. Live Dry-Run Evidence

Dry-run report:

- `.cache/reports/board_seed_dry_run_bog7.v1.json`

Accepted digest:

```text
5a217d0ea37be5fbfc4c20e796278749bb10652537819342752a527f40b332be
```

Planned actions:

- ensure required board labels;
- ensure BOG-7 issue;
- ensure ProjectV2 item on board `#5`;
- set `Status=Todo`;
- set `Faz=F5 Projection Drift`;
- set `Track=github-ops`;
- set `Priority=P1`;
- set `Kind=gate`.

## 7. Live Apply Evidence

Apply report:

- `.cache/reports/board_seed_apply_live.v1.json`

Observed result:

- Status: `OK`
- Created labels:
  - `blocked`
  - `gate`
  - `needs-verification`
  - `project-roadmap`
  - `quality`
  - `risk`
  - `security`
- Created issue:
  - `#78`
  - `https://github.com/Halildeu/autonomous-orchestrator/issues/78`
- Added ProjectV2 item:
  - `PVTI_lAHOCx7tY84Ba38Czgv-mxA`
- Set fields:
  - `Status=Todo`
  - `Faz=F5 Projection Drift`
  - `Track=github-ops`
  - `Priority=P1`
  - `Kind=gate`

Append-only issue evidence comment:

- `https://github.com/Halildeu/autonomous-orchestrator/issues/78#issuecomment-4725314501`

## 8. Live Verification Evidence

Seed-time issue verification:

- issue `#78` is `OPEN`;
- labels are `gate`, `project-roadmap`, and `quality`;
- body contains `agent-state:v1` and required board sections.

ProjectV2 item inventory:

```text
gh project item-list 5 --owner Halildeu --format json --limit 100
```

Observed:

- `totalCount=1`
- item issue number `78`
- item id `PVTI_lAHOCx7tY84Ba38Czgv-mxA`
- `status=Todo`
- `faz=F5 Projection Drift`
- `track=github-ops`
- `priority=P1`
- `kind=gate`

Post-seed live probe:

- `.cache/reports/board_live_probe_project5_after_seed.v1.json`
- ProjectV2 `#5` items_total: `1`
- Field compatibility: `OK`
- Missing fields/options: none

Post-BOG-9 governed verification state:

- issue `#78` remains `OPEN`;
- issue labels are now `gate`, `needs-verification`, `project-roadmap`, and
  `quality`;
- ProjectV2 item status is now `Needs Verify`;
- final live projection reports drift `0`;
- final live sync dry-run reports `noop=true`.
- verification evidence comment:
  `https://github.com/Halildeu/autonomous-orchestrator/issues/78#issuecomment-4725408977`.

## 9. Remaining Boundary

BOG-7 does not prove:

- BOG-7 implementation work is complete;
- issue `#78` should be closed;
- board item should be `Done`;
- runtime/user-path acceptance is complete.

Later gates proved live projection from GitHub issue/Project inventory and
promoted the item to `Needs Verify`. `Done` and issue closure remain out of
scope.

# Board Live Projection Evidence (v1)

Status: REVIEW_READY  
Scope: BOG-8 live board projection generation from GitHub issue and ProjectV2 inventory  
Generated: 2026-06-17  
Mode: read-only; no GitHub mutation

## 1. Purpose

BOG-8 replaces fixture-only projection evidence with a read-only live
projection generator.

The command reads:

- GitHub issues labeled `project-roadmap`;
- target ProjectV2 item inventory;
- target ProjectV2 field inventory.

It emits a schema-valid `board_projection.v1` report and drift summary.

## 2. Implemented Command

```text
python3 -m src.ops.manage board-projection-live
```

Allowed read-only commands:

- `gh auth status`
- `gh issue list`
- `gh project field-list`
- `gh project item-list`

Forbidden by design:

- issue creation/edit/close;
- label mutation;
- ProjectV2 item mutation;
- `Done` automation;
- projection apply.

## 3. Acceptance Boundary

BOG-8 is `REVIEW_READY` when:

- live projection command exists;
- fake-`gh` tests prove OK and mismatch paths;
- apply mode blocks before any `gh` call;
- live run against ProjectV2 `#5` emits a schema-valid projection;
- drift summary is recorded.

BOG-8 does not prove:

- live sync apply has run;
- issue `#78` can be closed;
- runtime/user-path acceptance is complete.

## 4. Local Contract Evidence

Implemented files:

- `src/ops/board/live_projection.py`
- `src/ops/commands/board_cmds.py`
- `tests/contract/test_board_live_projection.py`

Contract tests:

```text
python3 -m pytest tests/contract/test_board_live_projection.py -q
3 passed

python3 -m pytest tests/contract/test_board_setup.py tests/contract/test_board_sync.py tests/contract/test_board_apply.py tests/contract/test_board_live_probe.py tests/contract/test_board_metadata.py tests/contract/test_board_live_projection.py tests/contract/test_board_auth_preflight.py tests/contract/test_board_pr_merge.py tests/contract/test_board_commands.py tests/contract/test_board_projection.py tests/contract/test_board_seed.py -q
58 passed
```

Tested behavior:

- read-only live projection emits schema-valid `board_projection.v1`;
- fixture-free issue and ProjectV2 item inventory are compared;
- field mismatch creates `DIGEST_MISMATCH` drift;
- apply mode blocks before any `gh` call;
- no mutation command is emitted.

## 5. Live Projection Evidence

Live command:

```text
python3 -m src.ops.manage board-projection-live --repo Halildeu/autonomous-orchestrator --project-owner Halildeu --project-number 5 --mode dry-run --out .cache/reports/board_projection_live_project5.v1.json
```

Report:

- `.cache/reports/board_projection_live_project5.v1.json`

Observed result:

- Status: `OK`
- Expected items: `1`
- Observed board items: `1`
- Drift total: `0`
- Projection digest:

```text
417b90e0a78d9dc2be553182bc2384522b924523a2262750cf2a86fa15e0cb0c
```

Expected issue:

- issue `#78`
- title `BOG-7: Live board item population and sync acceptance`
- `Status=Needs Verify`
- `Faz=F5 Projection Drift`
- `Track=github-ops`
- `Priority=P1`
- `Kind=gate`
- labels `gate`, `needs-verification`, `project-roadmap`, `quality`

Observed ProjectV2 item:

- item id `PVTI_lAHOCx7tY84Ba38Czgv-mxA`
- issue `#78`
- fields and labels matched expected values.

Historical BOG-8 first-run digest before BOG-9 verification promotion:

```text
d0fa8838e08959d46d7bd6886645ffbd2796df657e28bf1cef49b6a0f01ae506
```

That earlier run proved live projection at seed state (`Status=Todo`). The
current snapshot above proves the same read-only projection after issue `#78`
was promoted to `Needs Verify`.

## 6. Next Boundary

The next safe gate was live sync validation:

- build or derive the ProjectV2 metadata map from live field/item ids;
- run `board-sync` dry-run against the live projection;
- require accepted projection digest before any sync apply;
- keep issue close and `Done` out of scope until acceptance evidence exists.

BOG-9 executed that boundary and left the item open in `Needs Verify`.

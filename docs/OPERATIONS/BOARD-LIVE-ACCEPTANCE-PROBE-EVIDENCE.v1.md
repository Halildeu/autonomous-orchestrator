# Board Live Acceptance Probe Evidence (v1)

Status: REVIEW_READY  
Scope: BOG-6A read-only GitHub ProjectV2 acceptance probe  
Generated: 2026-06-17  
Mode: report/read-only only; no GitHub Project, issue, PR, label, or field mutation is authorized by this evidence

## 1. Purpose

BOG-6A closes the remaining fake-work risk between local board automation and
real GitHub ProjectV2 readiness.

The probe proves only these live prerequisites:

- `gh` is installed and authenticated,
- the active account can read the target repo,
- the account can list GitHub Projects for the owner,
- a target ProjectV2 can be resolved by number or title,
- required board fields/options can be compared against the repo contract.

It deliberately does not create projects, edit fields, add issues, change
labels, move ProjectV2 items, close issues, or mark anything `Done`.

## 2. Implemented Command

Command:

```bash
python3 -m src.ops.manage board-live-probe
```

Read-only `gh` calls allowed by implementation:

- `gh auth status`
- `gh repo view`
- `gh project list`
- `gh project view`
- `gh project field-list`

Any other `gh` command path is rejected inside `src/ops/board/live_probe.py`
before execution.

If `--token-env <NAME>` is provided and present, the token value is copied only
into the child `gh` process as `GH_TOKEN`. The value is not written to reports.

## 3. Local Contract Evidence

Implemented files:

- `src/ops/board/live_probe.py`
- `src/ops/commands/board_cmds.py`
- `tests/contract/test_board_live_probe.py`
- `fixtures/board/board_live_probe_project_list.v1.json`
- `fixtures/board/board_live_probe_field_list.v1.json`

Contract test:

```text
python3 -m pytest tests/contract/test_board_live_probe.py -q
5 passed
```

Tested behavior:

- happy path is read-only,
- `apply` mode blocks before any `gh` call,
- auth failure blocks,
- missing target project reports `WARN`,
- field contract mismatch reports `WARN`,
- custom token env is available to fake `gh` as `GH_TOKEN`,
- token values are not present in command reports,
- fake `gh` call ledger contains only read-only prefixes.

Full board regression:

```text
python3 -m pytest tests/contract/test_board_commands.py tests/contract/test_board_apply.py tests/contract/test_board_projection.py tests/contract/test_board_pr_merge.py tests/contract/test_board_sync.py tests/contract/test_board_live_probe.py -q
35 passed
```

Core and governance gates:

```text
CORE_UNLOCK=1 CORE_UNLOCK_REASON='BOG-6A board live acceptance read-only probe implementation' python3 ci/core_ops_contract_test.py
{"status": "OK", "tests_passed": 10, "tests_failed": 0}

python3 ci/validate_schemas.py
OK

python3 -m src.ops.manage policy-check --source both
{"status": "OK", ...}

python3 -m src.ops.manage doc-nav-check --workspace-root .cache/ws_customer_default
{"status": "OK", ...}
```

## 4. Live Probe Evidence

Live repo probe:

```text
python3 -m src.ops.manage board-live-probe --repo Halildeu/autonomous-orchestrator --project-owner Halildeu
```

Report:

- `.cache/ws_customer_default/.cache/reports/board_live_probe.v1.json`

Observed live result:

- Status: `WARN`
- Auth account: `Halildeu`
- Required scopes present: `project`, `repo`
- Additional observed scopes: `gist`, `read:org`, `user`, `workflow`
- Repo: `Halildeu/autonomous-orchestrator`
- Repo permission: `ADMIN`
- Listed owner projects:
  - `#4 platform-ai - Faz 24 Meeting Intelligence`
  - `#3 Roadmap v5.0.0`
  - `#2 platform Roadmap`
- Target board title: `autonomous-orchestrator Governance Board`
- Blocking reason: `PROJECT_NOT_FOUND_BY_NUMBER_OR_TITLE`

This proves the account and repo access are sufficient for read-only discovery,
but the intended autonomous-orchestrator governance board does not currently
exist under the expected title.

## 5. Existing Board Comparison

Live comparison probe:

```text
python3 -m src.ops.manage board-live-probe --repo Halildeu/autonomous-orchestrator --project-owner Halildeu --project-number 2 --board-title 'platform Roadmap' --out .cache/reports/board_live_probe_platform_roadmap.v1.json
```

Report:

- `.cache/ws_customer_default/.cache/reports/board_live_probe_platform_roadmap.v1.json`

Observed live result:

- Status: `WARN`
- Resolved ProjectV2: `#2 platform Roadmap`
- Required fields present: `Status`, `Faz`, `Track`, `Priority`, `Kind`
- Contract mismatch:
  - `Faz` is missing autonomous-orchestrator adoption phase options.
  - `Track` is missing `core`, `github-ops`, `managed-repo`, `pm-suite`,
    `ui`, and `work-intake`.

This proves the metadata probe works against a real board. It also proves the
existing `platform Roadmap` board should not be silently reused for this repo
without an explicit board setup decision and field migration/change proposal.

## 6. Acceptance Boundary

BOG-6A is `REVIEW_READY` because:

- read-only live capability is implemented,
- fake-`gh` tests pass,
- live account/repo access is proven,
- live ProjectV2 owner inventory is proven,
- target board absence is visible and report-backed,
- existing board mismatch is visible and report-backed,
- no live mutation was made.

BOG-6A does not prove:

- a new autonomous-orchestrator governance ProjectV2 exists,
- ProjectV2 fields were created or edited,
- issues were added to a live board,
- labels were created or changed,
- live board sync apply succeeded,
- runtime/user-path acceptance is complete,
- human/operator acceptance is recorded.

## 7. Next Gate

The next safe gate is BOG-6B:

- create or select the real target board through an explicit operator-bound
  setup decision,
- capture the resulting ProjectV2 number/id,
- rerun `board-live-probe` until field compatibility is `OK`,
- then use the existing `board-projection` and `board-sync --mode dry-run`
  sequence before any apply.

# autonomous-orchestrator (WWV)

Bu repo, “request envelope → intent routing → workflow” akışını minimum çalışan bir iskelet olarak kurar.

## Yerel geliştirme

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python ci/validate_schemas.py
python ci/policy_dry_run.py --fixtures fixtures/envelopes --out sim_report.json
python -m src.orchestrator.local_runner --envelope fixtures/envelopes/0001.json --workspace . --out evidence
python -m src.ops.manage runs --limit 5
python ci/smoke_test.py
```

## Examples

```bash
python examples/sdk_run_demo.py
python examples/policy_check_demo.py
```

## CLI shortcut (no envelope file)

```bash
python -m src.cli run --intent urn:core:docs:policy_review --tenant TENANT-LOCAL --dry-run true --output-path policy_review.md
python -m src.cli run --intent urn:core:ops:dlq_triage --tenant TENANT-LOCAL --dry-run true --output-path dlq_triage.md
```

## CLI help / version

```bash
python -m src.cli --help
python -m src.cli run --help
python -m src.cli --version
```

Gerçek OpenAI çağrısı için (integration-only) `openai-ping` kullan:

```bash
python -m src.ops.manage openai-ping
# (Opsiyonel: pip ile install ettiysen) orchestrator ops openai-ping
```

## CI gate’leri

- `gate-schema`: JSON Schema + fixture instance doğrulaması
- `gate-secrets`: gitleaks ile secret scanning
- `gate-policy-dry-run`: fixture’lar üzerinden intent → workflow dry-run raporu

## Supply chain (CI)

- CI, GitHub Actions secret `SUPPLY_CHAIN_SIGNING_KEY` ister (Settings → Secrets and variables → Actions).
- Örnek key üret: `python -c "import secrets; print(secrets.token_hex(32))"`
- Yerelde `ci/smoke_test.py` için `DEV_KEY` fallback yeterli (deterministik).
- İstersen `SUPPLY_CHAIN_SIGNING_KEY` ortam değişkeniyle ya da `.env` ile set edebilirsin (`.env` git-ignored).

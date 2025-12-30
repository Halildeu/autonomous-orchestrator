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
python ci/smoke_test.py
```

## CI gate’leri

- `gate-schema`: JSON Schema + fixture instance doğrulaması
- `gate-secrets`: gitleaks ile secret scanning
- `gate-policy-dry-run`: fixture’lar üzerinden intent → workflow dry-run raporu

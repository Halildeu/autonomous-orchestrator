# Core vs Workspace (v0.3)

Bu doküman, “core ürün” ile “workspace (tenant/private)” ayrımını netleştirir.

## Neden?
- **Core**: generic, shippable, CI gate’li ürün kodu + schema/policy/workflow + runner/ops tooling.
- **Workspace**: tenant/customer/private kararlar ve artefact’lar (SSOT). Core’a doğrudan karışmaz.
- **Promotion lane**: workspace’te üretilen generic artefact’ları sanitize edip core’a “candidate” olarak almak.

## Core repo (public/shippable)
Core içinde tutulur:
- `src/` (runtime/ops tooling)
- `schemas/`, `policies/`, `workflows/`, `orchestrator/`, `registry/` (control plane SSOT)
- `roadmaps/SSOT/roadmap.v1.json` (kilitli SSOT roadmap)
- `ci/` (deterministik gate scriptleri)
- `docs/` (runbook, release strategy, side-effects manifest)

Core içinde **asla** commit edilmemesi gerekenler:
- `.env`
- `.cache/**`
- `evidence/**`
- `dlq/*.json`
- `dist/`

## Workspace root (tenant/private)
Workspace içinde tutulur (örnek yapı):
- `tenant/<TENANT>/decision-bundle.v1.json`
- `tenant/<TENANT>/{context,stakeholders,scope,criteria}.v1.md`
- `packs/`, `formats/`, `best_practices/`
- `incubator/` (promotion lane için aday artefact’lar)

## Roadmap Runner ile workspace seçimi
Roadmap Runner, step path’lerini workspace-root’a göre resolve eder:

```bash
python -m src.ops.manage roadmap-apply \
  --roadmap roadmaps/SSOT/roadmap.v1.json \
  --milestone M2 \
  --workspace-root /ABS/PATH/TO/WORKSPACE \
  --dry-run true \
  --dry-run-mode readonly
```

Kural (fail-closed):
- Workspace-root dışına yazma denemesi `WORKSPACE_ROOT_VIOLATION` ile durur.
- Readonly dry-run modda allowlisted gate’ler çalışır; workspace-root kirlenirse fail olur.

## Promotion lane (v0.3 scaffolding)
v0.3’te cross-repo PR/merge yok; sadece:
- `workspace-bootstrap` (template’ten workspace oluştur)
- `promote-scan` (incubator sanitize taraması; fail-closed)
- `workspace-sanitize` (paylaşım için runtime artefact temizliği)


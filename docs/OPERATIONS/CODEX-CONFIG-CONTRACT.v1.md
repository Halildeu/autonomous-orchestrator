# Codex Config Contract v1 (SSOT)

Bu dokuman repo icin deterministik Codex davranisini kilitler. Program-led calisma
modelini ve core_lock/ops/gate/runner zincirini korur.

## Expected Config (effective runtime)
- model: gpt-5.3-codex
- review_model: gpt-5.4
- model_provider: openai
- approval_policy: never
- sandbox_mode: workspace-write
- sandbox_workspace_write.network_access: false
- project_doc_max_bytes: 65536
- project_doc_fallback_filenames: ["AGENTS.md","AGENT-CODEX.md","TEAM_GUIDE.md"]
- model_reasoning_effort: medium
- model_reasoning_summary: auto
- model_verbosity: medium
- model_auto_compact_token_limit: 24000

## Instruction chain (SSOT)
- fallback only: AGENTS.md
- router: AGENTS.md icindeki SSOT Entrypoint Map

## Config resolution (deterministik)
- repo-local config template: <repo>/.codex/config.toml (Codex auto-load, proje trusted olmali)
- managed runtime overlay: <repo>/policies/policy_codex_runtime.v1.json
- auth: default global store (keyring veya file-backed fallback ~/.codex/auth.json); repo'ya kopyalanmaz
- interactive CLI'da CODEX_HOME manuel export ETMEYIN — credential bulunamaz ve 401 hatasi olusur
- program-led runner'lar icin CODEX_HOME yalnizca <WS>/.cache/codex_home/ yoluna set edilir (ic kullanim)
- tek gercek config: <WS>/.cache/codex_home/config.toml (program-led bootstrap)
- bootstrap, repo template + managed runtime overlay birlesiminden effective config uretir
- NOT: repo-local auto-read yalnizca template'i okur; overlay'i uygulamaz. Overlay yalniz orchestrator bootstrap ile workspace runtime'a yazilir
- Trust gereksinimi: repo-local config yuklenmediyse ~/.codex/config.toml icinde projeyi trusted isaretle

## Managed Runtime Overlay
- Overlay schema: schemas/policy-codex-runtime.schema.v1.json
- Overlay policy: policies/policy_codex_runtime.v1.json
- Template `.codex/config.toml` minimal ve geriye donuk tutulur; guncel effective davranis overlay ile kilitlenir.
- MCP / capability-catalog / automations sozlesmesi fail-closed baslar; policy bunlari `disabled` veya `planned` olarak ifade eder, runtime auto-enable yapmaz.
- Provider continuation icin `Responses API` zincirinde varsa `previous_response_id` workspace session context'ten okunur ve yeni `response_id` ayni session context'e geri yazilir.
- `model_auto_compact_token_limit` asildiginda orchestrator workspace altinda deterministic compaction özeti uretir ve session context icindeki `compaction` / `provider_state.summary_ref` alanlarini gunceller.

## Secrets (.env, no leaks)
- LLM saglayici anahtarlari .env veya process env icinden okunur (yalnizca var/yok durumu raporlanir).
- .env git-ignored; .env.example dummy degerlerle commit edilir.
- Anahtar degerleri log/evidence/response icinde yazilmaz.

## Doc-nav tek kapi (summary + strict ayrimi)
- summary (default) rapor: doc_graph_report.v1.json
- strict rapor: doc_graph_report.strict.v1.json (cockpit etkilemez)

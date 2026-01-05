# Codex Config Contract v1 (SSOT)

Bu dokuman repo icin deterministik Codex davranisini kilitler. Program-led calisma
modelini ve core_lock/ops/gate/runner zincirini korur.

## Expected Config (repo-local)
- model: gpt-5.2-codex
- approval_policy: never
- sandbox_mode: workspace-write
- sandbox_workspace_write.network_access: false
- project_doc_max_bytes: 65536
- project_doc_fallback_filenames: ["AGENTS.md","AGENT-CODEX.md","TEAM_GUIDE.md"]

## Instruction chain (SSOT)
- fallback only: AGENTS.md
- router: AGENTS.md icindeki SSOT Entrypoint Map

## CODEX_HOME (deterministik)
- repo-local config: <repo>/.codex/config.toml
- CODEX_HOME bu klasore ayarlanarak global configten bagimsiz calisir
- tek gercek config: <WS>/.cache/codex_home/config.toml (program-led bootstrap)

## Secrets (.env, no leaks)
- LLM saglayici anahtarlari .env veya process env icinden okunur (yalnizca var/yok durumu raporlanir).
- .env git-ignored; .env.example dummy degerlerle commit edilir.
- Anahtar degerleri log/evidence/response icinde yazilmaz.

## Doc-nav tek kapi (summary + strict ayrimi)
- summary (default) rapor: doc_graph_report.v1.json
- strict rapor: doc_graph_report.strict.v1.json (cockpit etkilemez)

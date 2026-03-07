# CODEX-CONFIG (safe local setup) — v0.1

Bu repo, Codex/agent’in **repo içindeki SSOT dokümanlarını** otomatik okumasını ve “kullanıcı komut yazmaz” modunu desteklemeyi hedefler.

Not:
- Bu repo içinden `~/.codex/config.toml` dosyanızı **değiştirmeyiz** (güvenlik).
- Aşağıdaki snippet’i **elle** kopyalayıp kendi ortamınıza uyarlayın.

## Önerilen snippet (minimal template)

```toml
# Project docs fallback
project_doc_max_bytes = 65536
project_doc_fallback_filenames = [
  "AGENTS.md",
  "docs/OPERATIONS/CODEX-UX.md",
  "docs/ROADMAP.md",
  "docs/OPERATIONS/release-strategy.md",
  "docs/OPERATIONS/core-vs-workspace.md",
  "docs/OPERATIONS/roadmap-runner-ssot-format.md",
]

# Safer defaults (recommended)
approval_policy = "never"
sandbox_mode = "workspace-write"

[sandbox_workspace_write]
network_access = false
```

Not:
- Effective davranis sadece bu snippet'ten gelmez.
- Program-led bootstrap, `policies/policy_codex_runtime.v1.json` icindeki managed runtime overlay'i `CODEX_HOME/config.toml` uzerine uygular.

## Notlar / güvenlik rehberi

- Network default kapalı tutun (`network_access = false`). Integration test gerektiğinde ayrı profil açın.
- Secrets’i config’e yazmayın. Yerelde `.env` kullanıyorsanız `.gitignore` altında olduğundan emin olun.
- Agent varsayılan workspace root’u `.cache/ws_customer_default` olarak kabul eder; customer workspace verisi core repo’ya yazılmaz.
- Effective config kontrolu ve drift denetimi `CODEX-CONFIG-CONTRACT.v1.md` + `policy_codex_runtime.v1.json` ile yapilir.

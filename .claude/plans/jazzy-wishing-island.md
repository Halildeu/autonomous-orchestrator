# Context Autopilot — Kendi Kendini Yöneten Bağlam Sistemi (v2 — Codex Revizyonlu)

## Context (Neden?)

Context Engine v2 altyapıyı kurdu ama **operasyonel döngü hala manuel**:
- Biten iş → memory güncellenmesi gerekiyor → kimse yapmıyor
- Yeni oturum → tech stack bilmiyor → React 18.2 mi 19 mu?
- PR merge → arşivleme gerekiyor → unutuluyor
- Domain değişikliği → versiyon kontrol edilmiyor → yanlış API/pattern
- Çok proje var → gruplanmamış → context switch'te kayıp

**Konumlandırma (R11):** Bu plan Context Engine v2'nin Phase 3.5+ uzantısıdır — yeni bir proje değil.

## Codex İstişare Revizyonları (12)

| # | Revizyon | Uygulama |
|---|---|---|
| R1 | Memory yolu `$CLAUDE_PROJECT_DIR` env var ile | Hardcoded path yok, env-based |
| R2 | Dev repo yolu `.cache/managed_repos.v1.json`'dan | Registry-first, hardcode yok |
| R3 | PostCompact'ta sadece lightweight check | Full sweep yalnız git merge/pull'da |
| R4 | Dış merge görünmez → bootstrap'ta freshness check | Her oturum başında stale tarama |
| R5 | Project cards domain_scope'tan ayrı eksen | `project_id` + `project_group` ayrı field |
| R6 | Scope guard'a `project` alanı ekle (domain'i override etme) | Schema genişletme |
| R7 | Memory frontmatter parser yaz | Yeni utility |
| R8 | Toplu arşiv yerine akıllı arşiv (git+memory+mtime) | Auto-archive = üç koşul birlikte |
| R9 | extension_registry + PM-SUITE contract'ı kullan | project_card_resolver bunların üstüne inşa |
| R10 | Pinned Versions = freshness katmanı | Mevcut kurallar korunur, versiyon üstüne eklenir |
| R11 | Context Engine v2 uzantısı olarak konumla | Yeni proje değil |
| R12 | Hook yalnız Claude Bash tool call görür | Bootstrap gate'te de kontrol |

---

## 5-Phase Plan (Revize)

### PHASE 1: Memory Hygiene Automation + Immediate Cleanup
**Amaç:** Memory güncellemesi otomatik olsun. Stale entry birikimasın.

#### 1.1 Memory Frontmatter Parser (R7)

**Yeni dosya:** `src/shared/memory_parser.py` (~80 lines)

```python
def parse_memory_file(path: Path) -> dict:
    """Parse Claude memory file with YAML frontmatter.
    Returns: {name, description, type, body}
    """

def list_memory_files(memory_dir: Path) -> list[dict]:
    """List all memory files with parsed metadata."""

def update_memory_index(memory_dir: Path) -> dict:
    """Sync MEMORY.md index with actual files on disk."""
```

YAML frontmatter parse: `---` blokları arasındaki key-value çiftleri.
Mevcut `compile_rules_digest._load_domain_rules()` sadece skip ediyor — bu parser key/value okuyacak.

#### 1.2 Memory Sweep Script

**Yeni dosya:** `scripts/memory_sweep.py` (~200 lines)

Memory yolunu `$CLAUDE_PROJECT_DIR` env var ile çöz (R1):
```python
_MEMORY_DIR = Path(os.environ.get(
    "CLAUDE_PROJECT_DIR",
    Path.home() / ".claude" / "projects"
)) / "memory"
```

Eğer env yoksa, `__file__` tabanlı repo root'tan `managed_repos.v1.json` kontrol et.

Ne yapar:
1. **Index sync:** MEMORY.md ↔ gerçek dosyalar karşılaştır
2. **Stale detection:** Active projelerin son güncelleme tarihini kontrol et
   - 30+ gün → WARN
   - Dosya git log'unda son commit tarihine bak
3. **Smart archive detection (R8):** Üç koşul birlikte true ise arşiv öner:
   - Memory içeriğinde "ALL DONE" / "DONE" / "ARCHIVED" / "MERGED" var
   - Git log'da ilgili PR merge edilmiş
   - Son 7 gün aktif değişiklik yok
4. **Duplicate detection:** Aynı `name` veya benzer `description` → birleştirme öner

Tetikleme:
```
PostToolUse: Bash(git merge*) → full sweep
PostToolUse: Bash(git pull*)  → full sweep
PostCompact                   → lightweight check only (R3)
Bootstrap gate                → freshness check (R4, R12)
```

Lightweight check (PostCompact): Sadece index sync + stale count raporu (< 2 saniye).
Full sweep (merge/pull): Stale + archive + duplicate analizi.

Çıktı: `.cache/reports/memory_sweep_report.v1.json`

#### 1.3 Bootstrap Gate Freshness Integration (R4, R12)

**Mevcut genişletme:** `ci/check_context_bootstrap.py`

Yeni adım: `_check_memory_freshness()`
- Dış merge'ler (GitHub UI, terminal) bootstrap gate sırasında yakalanır
- Memory'deki active projelerin stale durumunu kontrol et
- WARN: "3 proje 30+ gündür güncellenmemiş"

#### 1.4 Immediate Cleanup (Tek Seferlik — R8 Revizyonlu)

Codex'in uyarısına göre **toplu arşiv yerine akıllı değerlendirme:**

| Proje | Durum | Karar |
|---|---|---|
| `context_engine_v2` | Bugün teslim, PR merged | ARŞİVLE (done) |
| `theme_admin_rewrite` | ALL 6 phases done, PR merged | ARŞİVLE (done) |
| `chart_platform_p1` | P1+P2 done ama P3-B/C/D açık | KORU (active) |
| `openfga_migration` | Phase 1-4 done, PR bekliyor | KORU (merge bekliyor) |

Yeni referanslar (Phase 4'e taşındı — birlikte yapılacak):
- `reference_tech_stack.md`
- `reference_ports_map.md`
- `reference_backend_services.md`
- `reference_monorepo_structure.md`

#### 1.5 Hook Entegrasyonu

**Mevcut genişletme:** `.claude/settings.json`

```json
PostToolUse: [
  {"matcher": "Bash(git merge*)", "hooks": [
    {"type": "command", "command": "python3 scripts/memory_sweep.py --trigger merge"}
  ]},
  {"matcher": "Bash(git pull*)", "hooks": [
    {"type": "command", "command": "python3 scripts/memory_sweep.py --trigger pull"}
  ]}
]

PostCompact: [
  ..existing system_status restore..,
  {"type": "command", "command": "python3 scripts/memory_sweep.py --trigger compaction --lightweight"}
]
```

#### 1.6 Schema + Tests

**Yeni schema:** `schemas/memory-sweep-report.schema.v1.json` (~40 lines)
**Test:** `tests/contract/test_memory_sweep.py` — index sync, stale detection, smart archive
**Test:** `tests/contract/test_memory_parser.py` — frontmatter parse, key/value extraction

#### 1.7 DoD

- [ ] Memory frontmatter parser çalışıyor (name, description, type, body)
- [ ] MEMORY.md index otomatik senkronize
- [ ] Stale project 30+ gün → WARN
- [ ] Smart archive: 3 koşul birlikte true → arşiv önerisi
- [ ] git merge/pull hook tetikleniyor (full sweep)
- [ ] PostCompact lightweight check çalışıyor (< 2s)
- [ ] Bootstrap gate memory freshness kontrol ediyor
- [ ] 2 proje arşivlendi (context_engine_v2, theme_admin_rewrite)
- [ ] Contract testler yeşil

---

### PHASE 2: Tech Stack Auto-Discovery
**Amaç:** Agent her zaman doğru React/Vite/AG Grid versiyonunu bilsin.

#### 2.1 Tech Stack Extractor

**Yeni dosya:** `scripts/tech_stack_extract.py` (~150 lines)

Dev repo yolunu registry'den çöz (R2):
```python
def _resolve_dev_repo_root() -> Path | None:
    """Resolve dev repo from .cache/managed_repos.v1.json (registry-first)."""
    managed = load_json_or_default(
        _REPO_ROOT / ".cache" / "managed_repos.v1.json", {}
    )
    for repo in managed.get("repos", []):
        if repo.get("slug") == "dev":
            return Path(repo["local_root"])
    return None
```

Ne yapar:
1. Dev repo root'u `managed_repos.v1.json`'dan çöz (R2)
2. `web/package.json` + `web/apps/mfe-shell/package.json` oku
3. Kritik versiyonları parse et:
   ```json
   {
     "react": "~18.2.0",
     "vite": "8.0.3",
     "typescript": "^5.8.3",
     "ag_grid": "34.3.1",
     "tailwindcss": "4.2.2",
     "vitest": "^4.1.0",
     "node_engines": "20.x || 22.x",
     "design_system": "1.1.0",
     "keycloak_js": "^26.2.3",
     "react_router": "^6.27.0",
     "tanstack_query": "^5.90.10"
   }
   ```
4. `.cache/reports/tech_stack_discovery.v1.json`'a yaz
5. `reference_tech_stack.md` memory dosyasını güncelle

#### 2.2 Frontend Rules Versiyon Injection (R10)

**Mevcut genişletme:** `.claude/rules/frontend.md`

Mevcut kurallar korunur. Dosyanın sonuna freshness katmanı eklenir:
```markdown
## Pinned Versions (auto-updated from package.json)
- React: ~18.2.0 (NOT React 19 — migration not started)
- Vite: 8.0.3 (pnpm override enforced)
- TypeScript: ^5.8.3
- AG Grid: 34.3.1 (exact — pnpm override enforced)
- Tailwind CSS: 4.2.2 via @tailwindcss/vite
- Node.js: 20.x || 22.x
- @mfe/design-system: 1.1.0
```

#### 2.3 Compiler Tech Stack Section

**Mevcut genişletme:** `src/ops/context_compiler.py`

`compile_enforcement_context()` çıktısına `tech_stack` eklenir:
```json
{
  "tech_stack": {
    "react": "~18.2.0",
    "vite": "8.0.3",
    "ag_grid": "34.3.1",
    "source": "managed_repos.v1.json → dev/web/package.json",
    "last_discovered": "2026-04-04T..."
  }
}
```

#### 2.4 Bootstrap Freshness Check

**Mevcut genişletme:** `ci/check_context_bootstrap.py`

Tech stack discovery dosyası 24 saatten eski mi? Değiştiyse re-parse.

#### 2.5 Schema + Tests

**Yeni schema:** `schemas/tech-stack-discovery.schema.v1.json` (~40 lines)
**Test:** `tests/contract/test_tech_stack_extract.py` — parse, versiyonlar, freshness

#### 2.6 DoD

- [ ] Dev repo yolu `managed_repos.v1.json`'dan çözülüyor (R2)
- [ ] 10+ kritik versiyon parse ediliyor
- [ ] frontend.md'ye Pinned Versions bölümü ekleniyor
- [ ] Compiler çıktısında tech_stack section var
- [ ] Bootstrap sırasında freshness kontrol ediliyor
- [ ] reference_tech_stack.md otomatik güncelleniyor
- [ ] Contract test yeşil

---

### PHASE 3: Project Context Cards
**Amaç:** Her proje için bağlam kartı. Agent proje değiştirdiğinde doğru kartı yüklesin.

#### 3.1 Mevcut Altyapı Üzerine İnşa (R9)

Codex'in bulgusu: `extension_registry.py` + `feature_execution_contract.v1.json` zaten proje seviyesinde context taşıyor. Yeni resolver bunların üstüne kurulacak.

Mevcut:
- `extension_registry.py:_discover_manifests()` → project manifest'leri topluyor (ama henüz aktif değil)
- `feature_execution_contract.v1.json` → `change_path_globs`, `affected_modules`, `service_scopes` var

Yeni: Bu mevcut yapıları birleştiren resolver.

#### 3.2 Project Context Card Schema

**Yeni schema:** `schemas/project-context-card.schema.v1.json` (~60 lines)

```json
{
  "project_id": "dev-web-frontend",
  "project_group": "frontend",
  "name": "Dev Web Frontend (MFE Shell)",
  "repo_ref": "dev",
  "tech_stack_ref": ".cache/reports/tech_stack_discovery.v1.json",
  "conventions_ref": ".claude/rules/frontend.md",
  "ports": {"mfe-shell": 3000, "storybook": 6006, "keycloak": 8081},
  "active_decisions": ["chart-viz-engine-selection"],
  "related_projects": ["dev-web-backend", "orchestrator"],
  "memory_refs": ["project_design_system_roadmap.md"],
  "extension_ref": "PRJ-PM-SUITE"
}
```

#### 3.3 Project Card Resolver

**Yeni dosya:** `src/ops/project_card_resolver.py` (~200 lines)

Domain scope'tan AYRI eksen (R5):
```python
def resolve_project_card(
    target_path: str,
    workspace_root: Path
) -> dict:
    """Hedef dosyadan proje kartını çöz.

    İki bağımsız eksen:
    - domain_scope_engine → teknik domain (frontend, backend, database...)
    - project_card_resolver → proje bağlamı (dev-frontend, orchestrator...)

    Birbirini override etmez, birlikte çalışır.
    """
```

Path → Project mapping:
```python
_PROJECT_MAP = [
    (re.compile(r"^web/|^apps/|^packages/"), "dev-web-frontend"),
    (re.compile(r"^services/|^server/"), "dev-web-backend"),
    (re.compile(r"^src/ops/|^src/orchestrator/|^ci/|^scripts/"), "orchestrator"),
    (re.compile(r"^db/|^migrations/"), "workcube-db"),
]
```

#### 3.4 Compiler Entegrasyonu (R5)

**Mevcut genişletme:** `src/ops/context_compiler.py`

Çıktıya `project_card` section eklenir — `domain_scope`'tan AYRI:
```json
{
  "domain_scope": {"primary_domain": "frontend", "confidence": 0.92},
  "project_card": {"project_id": "dev-web-frontend", "project_group": "frontend", "ports": {...}}
}
```

#### 3.5 Scope Guard Project Tracking (R6)

**Mevcut genişletme:** `src/ops/scope_guard.py`

State'e yeni `project` alanı eklenir (mevcut `domains` alanı KORUNUR):
```json
{
  "declared_scope": {
    "files": [...], "max_files": 5, "domains": ["frontend"],
    "project": "dev-web-frontend"
  },
  "actual_scope": {
    "files_written": [...], "domains_touched": ["frontend"],
    "projects_touched": ["dev-web-frontend"]
  }
}
```

Proje değişikliğinde WARN: "Proje değişti: dev-web-frontend → orchestrator"

#### 3.6 Policy (Extension Registry Üstüne — R9)

**Yeni policy:** `policies/policy_project_cards.v1.json` (~80 lines)

Extension registry + feature_execution_contract referansları:
```json
{
  "groups": {
    "frontend": {
      "projects": ["dev-web-frontend", "dev-design-system"],
      "extension_ref": "PRJ-PM-SUITE",
      "shared_rules": ".claude/rules/frontend.md"
    },
    "backend": {
      "projects": ["dev-web-backend", "schema-service"],
      "extension_ref": "PRJ-KERNEL-API",
      "shared_rules": ".claude/rules/backend.md"
    },
    "orchestrator": {
      "projects": ["autonomous-orchestrator"],
      "shared_rules": ".claude/rules/src-ops.md"
    }
  },
  "resolution": {
    "source": "extension_registry + feature_execution_contract",
    "fallback": "path_based_map"
  }
}
```

#### 3.7 Schema + Tests

**Yeni schema:** `schemas/project-context-card.schema.v1.json`
**Yeni schema:** `schemas/policy-project-cards.schema.v1.json`
**Test:** `tests/contract/test_project_card_resolver.py`

#### 3.8 DoD

- [ ] Proje kartı schema tanımlı
- [ ] target_path → proje kartı otomatik çözümleniyor
- [ ] Domain scope ve project card AYRI eksenler (R5)
- [ ] Scope guard'da project tracking (R6)
- [ ] Extension registry + PM-SUITE contract kullanılıyor (R9)
- [ ] Compiler çıktısında project_card section var
- [ ] Proje değişikliğinde WARN
- [ ] Contract test yeşil

---

### PHASE 4: Consolidated References
**Amaç:** Dağınık bilgileri tek noktada topla.

#### 4.1 Reference Memory Dosyaları

**Yeni memory:** `reference_tech_stack.md`
```markdown
---
name: reference_tech_stack
description: Dev repo pinned tech stack — auto-updated by tech_stack_extract.py
type: reference
---

## Core (pnpm override enforced)
- React: ~18.2.0 (NOT 19)
- Vite: 8.0.3
- AG Grid: 34.3.1 (exact)
- TypeScript: ^5.8.3
- Node.js: 20.x || 22.x

## Frontend Ecosystem
- Tailwind CSS: 4.2.2 (@tailwindcss/vite)
- @mfe/design-system: 1.1.0
- Vitest: ^4.1.0
- React Router: ^6.27.0
- @tanstack/react-query: ^5.90.10
- Zod: ^3.25.76
- keycloak-js: ^26.2.3
```

**Yeni memory:** `reference_ports_map.md`
```markdown
---
name: reference_ports_map
description: Dev + orchestrator service port map
type: reference
---

## Dev Apps
- 3000: mfe-shell (main)
- 3001-3007: mfe-users, mfe-access, mfe-audit, mfe-reporting, mfe-ethic, mfe-suggestions
- 6006: Storybook

## Backend Services
- 8081: Keycloak (login only)
- 8096: SchemaLens (schema-service)

## Orchestrator
- 8787: Cockpit UI
- 8790: Cockpit API
```

**Yeni memory:** `reference_backend_services.md`
```markdown
---
name: reference_backend_services
description: All backend services with tech stack, ports, responsibilities
type: reference
---

- schema-service (SchemaLens): Java 21, Spring Boot, port 8096 — Workcube table discovery
- permission-service: OpenFGA — ALL authorization (not Keycloak)
- core-data-service: CRUD + ScopeFilterInterceptor
- report-service: DashboardQueryEngine — SQL reports (no alias, qualify ambiguous)
- Keycloak: Login only (port 8081)
```

**Yeni memory:** `reference_monorepo_structure.md`
```markdown
---
name: reference_monorepo_structure
description: Dev repo monorepo — apps, packages, design system exports
type: reference
---

## Apps (web/apps/)
mfe-shell, mfe-users, mfe-access, mfe-audit, mfe-reporting, mfe-ethic, mfe-suggestions, mfe-schema-explorer

## Packages (web/packages/)
auth, shared-http, design-system, shared-types, i18n-dicts, blocks, create-app, platform-capabilities, x-charts, x-data-grid, x-editor, x-form-builder, x-kanban, x-scheduler

## Design System Exports
.tokens, .primitives, .components, .patterns, .providers, .theme, .a11y, .performance, .headless, .icons, .advanced, .advanced/data-grid/setup, .form
```

#### 4.2 Proje Arşivleme (R8 — Akıllı)

Sadece gerçekten biten 2 proje:
- `project_context_engine_v2.md` → [ARCHIVED] (PR #60 merged, 41/41 DoD)
- `project_theme_admin_rewrite.md` → [ARCHIVED] (ALL 6 phases, PR merged)

#### 4.3 MEMORY.md Index Güncelleme

- 4 yeni referans eklenir
- 2 proje Archived'a taşınır
- Index dosya sırası: User → Feedback → Reference → Active → Archived

#### 4.4 DoD

- [ ] 4 referans dosyası oluşturuldu
- [ ] 2 proje arşivlendi
- [ ] MEMORY.md index senkron
- [ ] Tech stack versiyonları domain rules ile tutarlı

---

### PHASE 5: Session Lifecycle Hooks
**Amaç:** Tüm otomasyonu hook'lara bağla.

#### 5.1 Settings.json Hook Güncellemesi

```json
{
  "PostToolUse": [
    {"matcher": "Bash(git merge*)", "hooks": [
      {"type": "command", "command": "python3 scripts/memory_sweep.py --trigger merge"}
    ]},
    {"matcher": "Bash(git pull*)", "hooks": [
      {"type": "command", "command": "python3 scripts/memory_sweep.py --trigger pull"}
    ]},
    ...existing Write/Edit hooks...
  ],
  "PostCompact": [
    ...existing system_status restore...,
    {"type": "command", "command": "python3 scripts/memory_sweep.py --trigger compaction --lightweight"}
  ]
}
```

#### 5.2 Bootstrap Gate Genişletme

- Tech stack freshness (24h threshold)
- Memory freshness (stale project WARN)
- Project card loading (workspace'e göre)

#### 5.3 DoD

- [ ] git merge/pull → memory sweep tetikleniyor
- [ ] PostCompact → lightweight check
- [ ] Bootstrap → tech stack + memory freshness
- [ ] Tüm hook'lar mevcut zincirle çakışmıyor

---

## Implementation Sırası

```
Phase 1 + 4 birlikte ←── acil: memory temizlik + referanslar
  ↓
Phase 2 ←── tech stack discovery (versiyon sorunu)
  ↓
Phase 3 ←── project cards (gruplama + context switch)
  ↓
Phase 5 ←── hook'lara bağla (otomasyon)
```

## Toplam Deliverables

### Yeni Dosyalar (8)
| Dosya | Phase | ~Lines |
|-------|-------|--------|
| `src/shared/memory_parser.py` | 1 | 80 |
| `scripts/memory_sweep.py` | 1 | 200 |
| `scripts/tech_stack_extract.py` | 2 | 150 |
| `src/ops/project_card_resolver.py` | 3 | 200 |
| `policies/policy_project_cards.v1.json` | 3 | 80 |
| `schemas/memory-sweep-report.schema.v1.json` | 1 | 40 |
| `schemas/tech-stack-discovery.schema.v1.json` | 2 | 40 |
| `schemas/project-context-card.schema.v1.json` | 3 | 60 |

### Memory Dosyaları (6)
| Dosya | Phase | Tip |
|-------|-------|-----|
| `reference_tech_stack.md` | 4 | YENİ |
| `reference_ports_map.md` | 4 | YENİ |
| `reference_backend_services.md` | 4 | YENİ |
| `reference_monorepo_structure.md` | 4 | YENİ |
| `project_context_engine_v2.md` | 4 | → ARCHIVED |
| `project_theme_admin_rewrite.md` | 4 | → ARCHIVED |

### Mevcut Değişiklikler (6)
| Dosya | Phase |
|-------|-------|
| `.claude/settings.json` | 1, 5 |
| `.claude/rules/frontend.md` | 2 |
| `src/ops/context_compiler.py` | 2, 3 |
| `src/ops/scope_guard.py` | 3 |
| `ci/check_context_bootstrap.py` | 1, 2, 5 |
| `MEMORY.md` | 1, 4 |

### Tests (4)
| Test | Phase |
|------|-------|
| `test_memory_parser.py` | 1 |
| `test_memory_sweep.py` | 1 |
| `test_tech_stack_extract.py` | 2 |
| `test_project_card_resolver.py` | 3 |

## Riskler

| Risk | Etki | Mitigation |
|------|------|-----------|
| Dev repo erişilemez | Tech stack fail | `managed_repos.v1.json` fallback + graceful skip (R2) |
| Memory dosyası bozulması | Context kaybı | Atomic write + backup before edit |
| PostCompact çok sık tetiklenir | Yavaşlık | Lightweight mode < 2s (R3) |
| Dış merge görünmez | Stale memory | Bootstrap gate freshness check (R4, R12) |
| Project card ↔ domain scope çakışma | Yanlış context | Ayrı eksenler, override yok (R5) |
| Yanlış auto-archive | Aktif proje kaybı | 3 koşul birlikte (git+content+mtime) (R8) |

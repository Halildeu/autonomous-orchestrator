# AGENTS.md – Proje Genel Agent Talimatları

## 0. Decision Registry (MUST READ)

**Before modifying any code, check `decisions/registry.v1.json`.**

Active decision topics:
- `decisions/topics/zanzibar-openfga.v1.json` — Authorization architecture (OpenFGA, Keycloak, data enforcement)
- `decisions/topics/security-local-dev.v1.json` — Local dev auth rules (no JWT, permitAll)

Rules:
- FINAL decisions cannot be silently reverted
- Rejected alternatives (with tried_count) must NOT be retried without user approval
- Constraints in topic files are HARD RULES — violating them breaks the system
- Run `backend/scripts/doctor-zanzibar.sh --quick` before committing auth-related changes

## 0b. Authority durumu

- Canonical OPO kaynakları:
  - `standards.lock`
  - `docs/OPERATIONS/AI-MULTIREPO-OPERATING-CONTRACT.v1.md`
  - `docs/OPERATIONS/ARCHITECTURE-CONSTRAINTS.md`
  - `docs/OPERATIONS/CACHE-BOUNDARY-RULES.v1.md`
  - `docs/OPERATIONS/OPO-AUTHORITY-MAP.v1.md`
- Current delivery bağlamı:
  - `docs/03-delivery/PROJECT-FLOW.md`
  - `docs/03-delivery/STORIES/**`
  - `docs/03-delivery/ACCEPTANCE/**`
  - `docs/03-delivery/TEST-PLANS/**`
- Transition-active rehber katmanı:
  - authority map içinde tanımlı transition rehber seti
- Archive-reference:
  - authority map içinde tanımlı archive-reference seti

Çelişki durumunda:
- Canonical OPO kaynakları kazanır.
- Transition-active ve archive-reference katmanı yeni normatif kural yazmak için
  kullanılmaz.

## 0c. Local Gate Zorunluluğu (MUST)

- Git geçişi öncesi local gate zorunludur: commit, push, PR create akışları
  `scripts/run_local_gate_chain.sh` PASS artifact’i olmadan ilerleyemez.
- Canonical artifact:
  - `.cache/reports/local-gate-chain/status.json`
- Guard script:
  - `scripts/require_local_gate.sh`
- Standard installer:
  - `scripts/setup_local_git_hooks.sh`
- Git hook enforce:
  - `.githooks/pre-commit`
  - `.githooks/pre-push`
- Artifact mevcut worktree fingerprint ile eşleşmiyorsa stale kabul edilir ve
  local gate yeniden çalıştırılır.
- Local security zincirinde `NVD_API_KEY` gerekiyorsa agent önce mevcut shell
  env’i, yoksa repo `.env/.env.local` dosyalarını allowlist üzerinden okur;
  secret değerini loglamaz.

## 1. İş tipleri

- [BE]  → Backend endpoint / servis / job
- [WEB] → Web frontend ekran/bileşen
- [MOB] → Mobil frontend ekran/bileşen
- [AI]  → AI/ML model / servis / pipeline
- [DATA]→ SQL / rapor / ETL / pipeline
- [DOC] → Problem Brief / PRD / Tech Design / Story / Acceptance / Runbook

## 2. Temel okuma sırası

Her görevde önce:

1. `standards.lock`
2. `docs/OPERATIONS/AI-MULTIREPO-OPERATING-CONTRACT.v1.md`
3. `docs/OPERATIONS/OPO-AUTHORITY-MAP.v1.md`
4. `docs/03-delivery/PROJECT-FLOW.md` (iş bağlamı gerekiyorsa)
5. `docs/OPERATIONS/ARCHITECTURE-CONSTRAINTS.md` ve `docs/OPERATIONS/CACHE-BOUNDARY-RULES.v1.md`

Sonra domain rehberi gerekiyorsa transition-active katman authority map
üzerinden çözülür:

6. Çekirdek transition rehberi
7. Transition doküman indeksi ve süreç rehberi authority map üzerinden çözülür.

İş tipine göre ilgili alan transition rehberi ve layout/style dokümanları
yalnız rehber amaçlı kullanılır; canonical authority değildir.

### [BE] Backend işleri
- Backend transition rehberi
- İlgili layout/style rehberi transition indeksinden seçilir.

### [WEB] Web frontend işleri
- Web transition rehberi
- İlgili layout/style rehberi transition indeksinden seçilir.

### [MOB] Mobil frontend işleri
- Mobil transition rehberi
- İlgili layout/style rehberi transition indeksinden seçilir.

### [AI] AI/ML işleri
- AI/ML transition rehberi
- İlgili layout/style ve data governance rehberi transition indeksinden seçilir.

### [DATA] Data / rapor işleri
- Data transition rehberi
- İlgili layout/style ve naming rehberi transition indeksinden seçilir.

### [DOC] Doküman işleri
- Doküman transition rehberi
- docs/99-templates/* (şablonlar varsa)
- İlgili docs style rehberi transition indeksinden seçilir.

## 3. Varsayılan cevap formatı

Tüm teknik görevlerde:

- Keşif Özeti
- Tasarım
- Uygulama Adımları (sadece: dosya yolu + yapılacak değişiklik)

Sadece doküman işlerinde:

- Örneklerden Öğrenilenler
- Doküman Taslağı
- Uygulama Adımları

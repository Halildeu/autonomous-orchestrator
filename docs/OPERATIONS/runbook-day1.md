# Runbook: Day 1 (v1)

Bu runbook, repoda **şu an gerçekten çalışan** komutlara göre yazıldı. Tüm komutları repo root’ta çalıştır.

Not:
- Eğer sisteminde `python` yoksa `python3` veya `.venv/bin/python` kullan.
- Komutların çoğu network gerektirmez ve deterministik çalışacak şekilde tasarlanmıştır.
- Çoğu değişiklik `main`’e GitHub Release yayınlamadan iner; milestone release süreci için `docs/OPERATIONS/release-strategy.md`’ye bak.

## 1) Quick health check (copy‑paste)

```bash
python smoke_test.py

python -m src.ops.manage runs --limit 5
python -m src.ops.manage dlq --limit 5
python -m src.ops.manage suspends --limit 5
```

Beklenen (yüksek seviye):
- `smoke_test.py` sonunda `SMOKE_OK` yazdırır ve exit code `0` döner.
- `manage runs` evidence içinden son run’ları listeler (tabloda `integrity` kolonu vardır).
- `manage dlq` DLQ kayıtlarını listeler (`count=...`).
- `manage suspends` varsa suspend’leri listeler; yoksa `count=0`.

## 2) Evidence integrity (tamper‑evident)

Her run sonunda `evidence/<run_id>/integrity.manifest.v1.json` üretilir. Manifest, run klasöründeki manifest dışındaki tüm dosyalar için `sha256` içerir (path sıralı).

Bir run’ı doğrulama:

```bash
python -m src.evidence.integrity_verify --run evidence/<run_id>
```

Çıktı JSON ve exit code:
- `status=OK` (exit `0`): dosyalar mevcut ve hash’ler tutarlı.
- `status=MISSING` (exit `2`): manifest veya manifestte listelenen dosyalardan bazıları yok.
- `status=MISMATCH` (exit `3`): dosyalardan en az biri manifestteki hash ile uyuşmuyor (bytes değişmiş).

`MISMATCH` olursa ne yapmalı (Day‑1 pratik):
- Bu evidence run’ını “güvenilmez” kabul et (audit/replay için kullanma).
- Run klasöründe manuel edit olup olmadığını kontrol et (özellikle `summary.json`).
- İlgili envelope’u fixture/evidence kaynağından tekrar çalıştırıp yeni evidence üret (run_id idempotency’den gelebilir; gerekiyorsa idempotency key değiştir).
- Ops akışında, şüpheli run’ı raporla/karantinaya al (örn. governor quarantine ile ilgili intent/workflow’u durdur).

## 3) Handling suspends (approval / resume)

SUSPENDED run’ları bulma:

```bash
python -m src.ops.manage suspends --limit 10
```

SUSPENDED bir run’ı resume etme (approve=true):

```bash
python -m src.orchestrator.local_runner --resume evidence/<run_id> --approve true
```

Notlar:
- `--approve` verilmezse (veya `false`) runner non‑zero exit ile `APPROVAL_REQUIRED` döner.
- Resume akışı mevcut evidence içinden `request.json` ve `MOD_A` çıktısını kullanır ve **APPROVAL sonrası** devam eder (WWV’de pratikte `MOD_B` çalışır).
- `dry_run=true` ise resume sırasında da **asla write yapılmaz** (hard rule).

## 4) DLQ workflow

DLQ listesi:

```bash
python -m src.ops.manage dlq --limit 10
```

Tek DLQ kaydını gösterme:

```bash
python -m src.ops.manage dlq --show <file>
```

DLQ stage’leri (bugünkü sistemde görülebilecek):
- `ENVELOPE_VALIDATE`: request envelope JSON parse/schema validasyonu.
- `STRATEGY_VALIDATE`: strategy table / intent registry validasyonu.
- `WORKFLOW_VALIDATE`: workflow JSON iç validasyonları.
- `ROUTE`: intent route edilemiyor (unknown intent).
- `EXECUTION`: workflow çalışırken policy violation vb.
- `GOVERNOR`: quarantine / concurrency limit gibi governor blokları.
- `BUDGET`: budget invalid veya budget aşımı.
- `QUOTA`: tenant quota aşımı.

Güvenli veri notu:
- DLQ, tam envelope’u saklamak yerine **minimal envelope alanları** saklar (örn. request_id/tenant_id/intent/risk_score/dry_run/side_effect_policy + idempotency hash). Ama yine de DLQ’yu “operasyon datası” olarak düşün.

## 5) Governor controls

Konfigürasyon dosyası:
- `governor/health_brain.v1.json`

`global_mode = "report_only"`:
- Runner MOD‑A + APPROVAL gibi read‑only akışları yürütür.
- MOD‑B’nin dosya yazması **override edilerek engellenir** (dry_run=false olsa bile).
- Evidence summary’de `governor_mode_used` alanında görünür.

Quarantine (intent veya workflow):
- `quarantine.intents` içine intent URN ekle → o intent ile gelen run’lar FAIL olur.
- `quarantine.workflows` içine workflow_id ekle → route edilen workflow bloklanır.
- Quarantine blokları DLQ’da `stage="GOVERNOR"` ve `POLICY_VIOLATION` olarak görünür (mesajda `QUARANTINED_*`).

Concurrency lock (WWV):
- Runner concurrency cap için `.cache/governor_lock` kullanır.
- Lock mevcutsa, yeni run `CONCURRENCY_LIMIT` ile FAIL olur (DLQ stage `GOVERNOR`).
- Güvenli temizleme:
  - Aktif runner olmadığından eminsen `.cache/governor_lock` dosyasını sil.

## 6) Budget & Quota

Budget ihlali örnekleri (policy_violation_code):
- `BUDGET_TOKENS_EXCEEDED`
- `BUDGET_TIME_EXCEEDED`
- `BUDGET_ATTEMPTS_EXCEEDED` (WWV’de MOD‑A attempt sayımı)

Quota ihlali örnekleri (policy_violation_code):
- `QUOTA_RUNS_EXCEEDED`
- `QUOTA_TOKENS_EXCEEDED`

Nereden bakılır:
- `evidence/<run_id>/summary.json` içinde `policy_violation_code` ve `budget_*` / `quota_*` alanları.
- DLQ kaydında `stage="BUDGET"` veya `stage="QUOTA"` olarak sınıflanır.

Nasıl ayarlanır:
- Per‑request: envelope içindeki `budget` alanı (fixtures/envelopes örneklerine bak).
- Tenant quota policy: `policies/policy_quota.v1.json`

## 7) Supply chain gates (SBOM + signing stub + verify + license + CVE)

CI gereksinimi:
- GitHub Actions secret olarak `SUPPLY_CHAIN_SIGNING_KEY` gerekir (repo Settings → Secrets and variables → Actions).
- Secret yoksa gate-schema, “Missing SUPPLY_CHAIN_SIGNING_KEY GitHub Actions secret” ile fail eder.

Local çalıştırma (ops/debug):

```bash
export SUPPLY_CHAIN_SIGNING_KEY="..."   # local dev’de .env de kullanılabilir (git ignored)

python supply_chain/sbom.py
python supply_chain/sign.py
python supply_chain/verify.py

python supply_chain/license_gate.py
python supply_chain/cve_gate.py
```

Not:
- Local smoke’ta DEV_KEY fallback olabilir; CI’da gerçek key beklenir.

## 8) Reaper / retention (GC)

Retention policy dosyası:
- `policies/policy_retention.v1.json`

Dry-run (silmez, sadece rapor üretir):

```bash
python -m src.ops.reaper --dry-run true --out reaper_report.json
```

Delete (siler, rapor üretir):

```bash
python -m src.ops.reaper --dry-run false --out reaper_report_delete.json
```

Ops shortcut (özet satırı):

```bash
python -m src.ops.manage reaper --dry-run true
```

Reaper kapsamı (bugünkü sistem):
- Evidence: `evidence/**/summary.json` olan run klasörleri (finished_at → started_at).
- DLQ: `dlq/*.json` (timestamp prefix varsa onu kullanır; yoksa mtime).
- Cache: `.cache/**` altındaki dosyalar (mtime).

## 9) Integration checks (OpenAI ping)

Bu komut **yalnızca entegrasyon testi** içindir; evidence run üretmez. (İstersen `.cache/openai_ping_last.json` yazar.)

Geçici olarak OpenAI çağrısını açma (prod için değil; debug):

1) `policies/policy_security.v1.json` içinde:
- `network_access: true`
- `network_allowlist: ["api.openai.com"]`

2) `policies/policy_secrets.v1.json` içinde `OPENAI_API_KEY` allowlist’te olmalı (default öyle).

3) Secret set et (env veya `.env`):

```bash
export OPENAI_API_KEY="..."   # value yazdırma / commit etme
python -m src.ops.manage openai-ping --timeout-ms 5000
```

Test sonrası güvenlik için:
- `network_access` tekrar `false` yap.

## 10) Policy review report (MOD_POLICY_REVIEW)

Sistemde yeni bir intent var:
- `urn:core:docs:policy_review`

Bu intent, repo içindeki policy-check çıktılarından bir **POLICY_REPORT.md** üretir ve (dry_run=false + policy izinliyse) dosyaya yazdırabilir.

Dry-run (dosyaya yazmaz, sadece planlar; report `.cache` altında üretilir):

```bash
python -m src.orchestrator.local_runner \
  --envelope fixtures/envelopes/0900_policy_review.json \
  --workspace . \
  --out evidence/
```

Beklenen:
- `.cache/policy_review/POLICY_REPORT.md` oluşur.
- Evidence node çıktısında `side_effects.would_write` görülür (dry_run hard rule).

Dosyaya yazdırmak için (low-risk örnek):
- Envelope’da `dry_run=false` ve `side_effect_policy="draft"` kullan.
- `context.output_path` vermezsen default hedef: `reports/POLICY_REVIEW.md`
- Risk threshold üstüyse run `SUSPENDED` olur; `--resume ... --approve true` ile MOD_B yazmayı tamamlar.

## 11) GitHub PR side effect (integration-only)

Bu özellik **gerçek bir yan etki** üretir (GitHub PR açar). Default olarak fail-closed’tur:
- `ORCH_INTEGRATION_MODE=1` set edilmezse **asla** gerçek HTTP yapılmaz (`INTEGRATION_MODE_REQUIRED`).

Ops seviyesinde en güvenli test (evidence üretmez):

1) `policies/policy_security.v1.json` içinde geçici olarak:
- `network_access: true`
- `network_allowlist: ["api.github.com"]`

2) `policies/policy_secrets.v1.json` içinde `GITHUB_TOKEN` allowlist’te olmalı (default: yes).

3) Env set et (değerleri yazdırma/commit etme):

```bash
export ORCH_INTEGRATION_MODE=1
export GITHUB_TOKEN="..."   # GitHub classic token veya fine-grained token (repo perms gerekir)

python -m src.ops.manage github-pr-test \
  --repo owner/name \
  --head branch-name \
  --base main \
  --title "autonomous-orchestrator: test PR" \
  --draft true
```

Test sonrası güvenlik için:
- `policies/policy_security.v1.json` içinde `network_access` tekrar `false` yap.

Not (orchestrated PR, advanced):
- Envelope `side_effect_policy="pr"` ve `dry_run=false` ise, PR oluşturma **yalnızca APPROVAL geçtikten sonra** (gerekirse `--resume ... --approve true`) MOD_B aşamasında denenir.
- Gerekli context alanları: `context.pr_repo`, `context.pr_head` (opsiyonel: `pr_base/pr_title/pr_body/pr_draft`).

# Otonom Üretim Hattı Yol Haritası
Deterministik Control Plane + Kısıtlı AI Execution Plane + Sürekli Öğrenme (Final v2.7)

Bu doküman, projeyi uçtan uca birlikte yürütürken “bağlamı kaybetmemek” için tek kaynak (SSOT) yol haritasıdır.

## İçindekiler

- [Otonom Üretim Hattı Yol Haritası](#otonom-üretim-hattı-yol-haritası)
  - [İçindekiler](#i̇çindekiler)
  - [0) Sistem Anayasası (Başlamadan kilitlenecek kurallar)](#0-sistem-anayasası-başlamadan-kilitlenecek-kurallar)
    - [0.1 Temel ilke](#01-temel-ilke)
    - [0.2 Normatif dil](#02-normatif-dil)
    - [0.3 Control plane değişiklik yönetimi (MUST)](#03-control-plane-değişiklik-yönetimi-must)
    - [0.4 Güvenlik \& Etik çerçeve (MUST)](#04-güvenlik--etik-çerçeve-must)
    - [0.5 Veri sınıflandırma \& gizlilik (MUST)](#05-veri-sınıflandırma--gizlilik-must)
    - [0.6 Threat model \& trust boundaries (MUST)](#06-threat-model--trust-boundaries-must)
    - [0.7 Kriptografik bütünlük \& değiştirilemezlik (MUST)](#07-kriptografik-bütünlük--değiştirilemezlik-must)
    - [0.8 Orchestrator Decisioning (MUST) — “Tek Komut” Deneyimi](#08-orchestrator-decisioning-must--tek-komut-deneyimi)
    - [0.9 Intent Contract (MUST)](#09-intent-contract-must)
    - [0.10 Context Strategy \& Token Pruning (MUST)](#010-context-strategy--token-pruning-must)
    - [0.11 Naming Convention Standard (MUST)](#011-naming-convention-standard-must)
    - [0.12 Policy Simulation \& Dry-Run Gate (MUST for medium/high risk)](#012-policy-simulation--dry-run-gate-must-for-mediumhigh-risk)
  - [Faz-0: Guardrail-First Starter Kit (Schema + Security + Ethics + Bias + Data + Intent)](#faz-0-guardrail-first-starter-kit-schema--security--ethics--bias--data--intent)
    - [Amaç](#amaç)
    - [Çıktılar](#çıktılar)
  - [Faz-0.25: Uygulama Disiplini (WWV + Workshop + Day-1 Ops) (SHOULD)](#faz-025-uygulama-disiplini-wwv--workshop--day-1-ops-should)
    - [Amaç](#amaç-1)
    - [Çıktılar](#çıktılar-1)
  - [Faz-0.5: Risk Scoring + HITL (Approval)](#faz-05-risk-scoring--hitl-approval)
  - [Faz-1: SSOT + Idempotency + Side-Effect Ledger + Progressive Autonomy](#faz-1-ssot--idempotency--side-effect-ledger--progressive-autonomy)
  - [Faz-1.5: Governor + Cost Control + Graceful Degradation + Hot-fix Override](#faz-15-governor--cost-control--graceful-degradation--hot-fix-override)
  - [Faz-2: Evidence + Provenance + Compliance + Artifact Store + Observability + GC](#faz-2-evidence--provenance--compliance--artifact-store--observability--gc)
    - [+ Integrity Verify (MUST)](#-integrity-verify-must)
  - [Faz-3: Discovery + Cost-aware Routing + Autoscaling](#faz-3-discovery--cost-aware-routing--autoscaling)
    - [+ Model Version Pinning (MUST)](#-model-version-pinning-must)
  - [Faz-3.5: Dual-Run \& Geçiş Yönetimi](#faz-35-dual-run--geçiş-yönetimi)
  - [Faz-4: Workflow Orchestrator (DAG) + Suspend/Resume + Konsol + DLQ (MUST)](#faz-4-workflow-orchestrator-dag--suspendresume--konsol--dlq-must)
    - [+ Decision Policy + State Machine (MUST)](#-decision-policy--state-machine-must)
  - [Faz-5: Executor (Sandbox) + Capability Enforcement + GPU/Virtualization + Env Caching](#faz-5-executor-sandbox--capability-enforcement--gpuvirtualization--env-caching)
    - [+ Context Engine + Local Runner + JIT Secrets](#-context-engine--local-runner--jit-secrets)
  - [Faz-6: Security \& Supply Chain + Multi-tenant Fairness/Quota + FinOps + Data Poisoning](#faz-6-security--supply-chain--multi-tenant-fairnessquota--finops--data-poisoning)
  - [Faz-7: AI Testing + Evals + Shadow Mode + Feedback + Governor Öğrenmesi](#faz-7-ai-testing--evals--shadow-mode--feedback--governor-öğrenmesi)
  - [Faz-8: Ürünleştirme (UI + SDK + Marketplace)](#faz-8-ürünleştirme-ui--sdk--marketplace)
  - [Faz-9: Kurumsal Ölçek (SLA, DR, HA, Billing, Sürdürülebilirlik)](#faz-9-kurumsal-ölçek-sla-dr-ha-billing-sürdürülebilirlik)
  - [Kırmızı Bayraklar](#kırmızı-bayraklar)
  - [Başlama Stratejisi (Son karar)](#başlama-stratejisi-son-karar)

---

## 0) Sistem Anayasası (Başlamadan kilitlenecek kurallar)

### 0.1 Temel ilke

- Control plane deterministik: Registry + Policy + Schemas + Gates + DAG + Governor + Orchestrator Decisioning
- Execution plane kısıtlı: AI yalnızca node executor (ve opsiyonel ranker), policy/gate aşamaz
- Her şey sözleşmeli: Request Envelope → Node Input → Node Output (JSON)
- Replayability: Evidence + Provenance + Compliance + Trace her run’da zorunlu
- Fail-closed: şüphede dur, mod düşür, karantinaya al
- Operasyonel gerçekler çekirdeğe dahildir: DLQ, GC, model pinning

### 0.2 Normatif dil

- MUST = olmazsa olmaz
- SHOULD = güçlü öneri
- MAY = opsiyonel

### 0.3 Control plane değişiklik yönetimi (MUST)

- Değişiklik sınıfları: low / medium / high risk
- Canary tenant/workflow + otomatik rollback kriterleri
- Backup/restore + DR hedefleri (RPO/RTO)
- Medium/High değişikliklerde: Policy Simulation & Dry-Run raporu zorunlu (bkz. [0.12](#012-policy-simulation--dry-run-gate-must-for-mediumhigh-risk))

### 0.4 Güvenlik & Etik çerçeve (MUST)

- Policy-as-code (OWASP/SAIF çizgisi)
- Etik gates + bias detection MUST
- Prompt injection / tool abuse / data poisoning riskleri için test+gate yaklaşımı

### 0.5 Veri sınıflandırma & gizlilik (MUST)

- Her run için `data_classification` zorunlu (public/internal/confidential/PII)
- Redaction/DLP kuralları policy ile yönetilir (log/evidence/feedback dahil)
- Tenant izolasyonu + şifreleme (in-transit / at-rest)

### 0.6 Threat model & trust boundaries (MUST)

- Control plane / execution plane / tool gateway / artifact store trust boundary dokümanı zorunlu
- High risk değişikliklerde threat model güncellenir

### 0.7 Kriptografik bütünlük & değiştirilemezlik (MUST)

- Registry/policy/workflow + evidence/ledger için signing/attestation zorunlu
- Evidence pack tamper-evident olmalı (hash-chain/Merkle + verify)
- Prod kritik kayıtları için append-only / WORM hedeflenir

### 0.8 Orchestrator Decisioning (MUST) — “Tek Komut” Deneyimi

Orchestrator deterministik olarak:

1. Komutu Request Envelope’a çevirir
2. Hangi workflow/modüller çalışacak seçer (Discovery)
3. DAG’i seçer/üretir (Planner; dynamic expansion MAY)
4. Paralel mi sıralı mı yürüneceğini belirler (Scheduler)
5. Her adımı gate’lerden geçirir (Gatekeeper)
6. Evidence/Provenance/Trace üretip run’ı kapatır

5 “beyin”:

- Planner
- Discovery
- Scheduler
- Governor
- Gatekeeper

### 0.9 Intent Contract (MUST)

- `intent` serbest string değildir; kontrollü set (URN/enum/registry).
- Örn: `urn:core:summary:summary_to_file`
- Orchestrator `intent → workflow` eşlemesini sadece bu setten yapar.
- Unknown intent = CI FAIL.

### 0.10 Context Strategy & Token Pruning (MUST)

- Her modül için registry’de `context_strategy`: raw/summarize/sliding_window/rag/hybrid
- Executor input limitini aşarsa stratejiyi otomatik uygular ve evidence’a yazar.
- “Sessiz taşma” yok.

### 0.11 Naming Convention Standard (MUST)

- Schema dosyaları: `kebab-case.schema.json`  
  Örn: `request-envelope.schema.json`, `registry-item.schema.json`
- Instance dosyaları: `snake_case.vX.json`  
  Örn: `registry.v1.json`, `policy_security.v1.json`, `wf_core.v1.json`
- ID formatları (JSON içi): `UPPER_SNAKE_CASE`  
  Örn: `MOD_CORE_SUMMARIZE`, `WF_CORE_PIPE`

### 0.12 Policy Simulation & Dry-Run Gate (MUST for medium/high risk)

Amaç: Yeni policy/registry/workflow/strategy değişikliği merge edilmeden önce etkisini görmek.

- CI’da “dry-run simulation” çalışır:
  - geçmiş X günün request envelope’ları (veya yoksa fixture set) üzerinde
  - side_effect_policy zorla `none` (simülasyon asla gerçek yan etki üretmez)
  - output: “kaç run allow/block/degrade/suspend olurdu?” raporu + örnekler
- Canary/traffic shifting kararlarını besler.
- Medium/High risk değişikliklerde rapor zorunlu, low risk’te SHOULD.

DoD: Policy değişikliği “neye ne yapıyor” bilinmeden merge edilmez (medium/high).

---

## Faz-0: Guardrail-First Starter Kit (Schema + Security + Ethics + Bias + Data + Intent)

### Amaç

AI çalıştırmadan önce güvenlik/etik/veri/intent + şema omurgasını kurmak.

### Çıktılar

1) `schemas/` (minimum)

- `registry-item.schema.json`
- `request-envelope.schema.json` (intent + risk + budget + data_classification)
- `intent-registry.schema.json`
- `node-output-base.schema.json`
- `quality-criteria.schema.json`
- `approval-policy.schema.json`

2) `policies/` (minimum)

- `policy_security.v1.json`
- `policy_ethics.v1.json` (bias detection MUST)
- `policy_data.v1.json` (DLP/redaction/retention)
- `policy_default.v1.json` (cost + degradation steps)

3) CI gates

- schema validation
- secret scanning
- SAST baseline
- ethics+bias simulation
- data policy simulation
- intent contract gate
- policy simulation dry-run gate (en az fixture set ile)

DoD: AI çalışmadan önce schema+security+ethics+bias+data+intent kapıları var.

---

## Faz-0.25: Uygulama Disiplini (WWV + Workshop + Day-1 Ops) (SHOULD)

### Amaç

“Başarı tuzakları”na düşmeden ilerlemek.

### Çıktılar

1) WWV (Worst Working Version) yaklaşımı (SHOULD)

- Faz-0’da aylar kaybetmemek için minimum sözleşme ile çekirdeği koştur:
  - Envelope v0.1: id + intent + risk_score (+ budget minimal)
  - data_classification v1.1’e genişleyebilir (ama hedef yine MUST)

2) Başlangıç Workshop (SHOULD)

- 1 günlük oturum: planı değil, çekirdek mini workflow’u tahtada çizin.
- intent URN, context_strategy alanı, approval davranışı somutlaştırılır.

3) Day-1 Operasyon Sahipliği (SHOULD → Faz-1.5 başlamadan MUST)

- Governor/DLQ/GC izleme-alarm-runbook sahibi atanır.
- Runbook skeleton’ı yazılmadan Governor “prod niyetiyle” başlamaz.

DoD: Herkes aynı “sözleşmeyi” anlar; operasyon bileşenleri sahipsiz kalmaz; WWV ile hızlı koşar.

---

## Faz-0.5: Risk Scoring + HITL (Approval)

Çıktılar

- `risk_score` + `risk_context`
- HITL policy + escalation matrix + timeout
- Approval node

---

## Faz-1: SSOT + Idempotency + Side-Effect Ledger + Progressive Autonomy

Çıktılar

- Envelope: `idempotency_key`, `budget`, `dry_run`, `side_effect_policy`, `risk_score`, `data_classification`, `intent`
- Idempotency store
- Side-effect ledger (hash + timestamp)
- Progressive autonomy (manual/human_review/full_auto) + eşikler

---

## Faz-1.5: Governor + Cost Control + Graceful Degradation + Hot-fix Override

Çıktılar

- Governor health brain + quarantine + global override
- Cost policy + fallback + degradation_steps
- Hot-fix override (config injection)

---

## Faz-2: Evidence + Provenance + Compliance + Artifact Store + Observability + GC
### + Integrity Verify (MUST)

Çıktılar

- Evidence pack + provenance + manifests + compliance
- OTel (trace_id/run_id)
- GC/Reaper job
- Integrity:
  - hash-chain/Merkle + signing/attestation + verifier

Verify konumu (MUST)

- CI: `evidence_verify_test` (üret → verify → PASS)
- Runtime: Konsol/audit aracı evidence açarken otomatik verify + sonucu gösterir

---

## Faz-3: Discovery + Cost-aware Routing + Autoscaling
### + Model Version Pinning (MUST)

Çıktılar

- In-memory indeks + refresh
- Hard filter → score → AI tie-break MAY (kısa listede)
- Cost-aware routing
- Autoscaling triggers
- Model pinning: “latest” yasak + CI gate + deprecation takvimi

---

## Faz-3.5: Dual-Run & Geçiş Yönetimi

Çıktılar

- Dual-writer gateway
- Reconciliation (parity/latency/error delta)
- Traffic shifting + rollback
- Parity Gate + Stability Gate

---

## Faz-4: Workflow Orchestrator (DAG) + Suspend/Resume + Konsol + DLQ (MUST)
### + Decision Policy + State Machine (MUST)

Çıktılar

- DAG scheduling + state store
- State machine: RUNNING/SUSPENDED/FAILED/COMPLETED
- Fail handling: retry → fallback → DLQ/SUSPEND
- Yönetim konsolu: SUSPENDED list + aksiyon + integrity verify sonucu
- DLQ: poison pill N fail → DLQ + alarm → governor degrade

---

## Faz-5: Executor (Sandbox) + Capability Enforcement + GPU/Virtualization + Env Caching
### + Context Engine + Local Runner + JIT Secrets

Çıktılar

- Capability model + Tool Gateway enforcement
- GPU/virtualization resource_profile
- Env caching
- Context Strategy Engine (MUST)
- Just-in-Time Secret Injection (MUST): Vault/Secrets Manager’dan session bazlı, RAM’e, loglarda yok
- Local Runner CLI (SHOULD): yerelde docker içinde modül/workflow test

---

## Faz-6: Security & Supply Chain + Multi-tenant Fairness/Quota + FinOps + Data Poisoning

Çıktılar

- CVE scan + image scan + license gate + SBOM (prod/dış müşteri MUST)
- Signing + verification (prod/dış müşteri MUST)
- Data poisoning + prompt injection gates
- Security Event → Response workflows
- Multi-tenant quotas + fairness scheduler
- FinOps gates + cost dashboards
- Output sanitization

---

## Faz-7: AI Testing + Evals + Shadow Mode + Feedback + Governor Öğrenmesi

Çıktılar

- Golden/regression/adversarial
- Rule+judge hibrit eval + versioning + canary
- Shadow mode
- Kullanıcı feedback MUST (DLP/redaction dahil)
- Governor policy optimization loop

---

## Faz-8: Ürünleştirme (UI + SDK + Marketplace)

Çıktılar

- Internal UI (MUST)
- SDK + module kit + signing
- External: tenant onboarding, quotas/cost, SLA görünürlüğü

---

## Faz-9: Kurumsal Ölçek (SLA, DR, HA, Billing, Sürdürülebilirlik)

Çıktılar

- SLA/SLO + error budget
- DR: RPO/RTO, warm standby, restore test, break-glass (MUST)
- Billing/metering
- Multi-region (SHOULD → büyüdükçe MUST)
- Enerji optimizasyonu SHOULD (green mode)

---

## Kırmızı Bayraklar

- Policy simülasyonu yoksa: “ne yaptığını bilmeden” policy merge edilir → felaket
- WWV yoksa: Faz-0’da aylar kaybolur
- Workshop yoksa: intent/context gibi kavramlarda sessiz anlaşmazlık çıkar
- Day-1 Ops sahibi yoksa: governor/DLQ/GC sahipsiz kalır, sistem sessizce bozulur
- Naming standard yoksa: JSON ormanında kaos çıkar

---

## Başlama Stratejisi (Son karar)

Çekirdek Mini Workflow (MUST)

MOD-A → APPROVAL → MOD-B

- MOD-A: Markdown oku → özet JSON
- APPROVAL: risk_score’a göre dur/geç
- MOD-B: dosyaya yaz (side_effect_policy=file_write/draft)

Not: local_runner.py büyüyor; bu kötü değil ama bir noktada “işlevleri modüllere bölme” refactor’u lazım olacak. Onu “işlev bozmadan” ayrı sprint olarak yapalım.
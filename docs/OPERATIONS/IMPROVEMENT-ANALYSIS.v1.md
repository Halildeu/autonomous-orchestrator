# IMPROVEMENT-ANALYSIS v1 — autonomous-orchestrator

Tarih: 2026-03-26
Durum: Analiz raporu (kod degisikligi yok)
Oncelik referansi: P0-P3 improvement priorities (mutabik kalinan siralama)

---

## 1. P0 — Crash Consistency & Data Integrity

### 1.1 Mevcut Durum

| Bilesen | Dosya | Mekanizma | Guclu | Zayif |
|---------|-------|-----------|-------|-------|
| Atomic write | `src/shared/utils.py` | tmp + rename | POSIX atomik rename | fsync yok; OS buffer flush oncesi crash = veri kaybi |
| Governor lock | `src/orchestrator/runner_config.py` | `O_CREAT\|O_EXCL` | Exclusive creation atomik | Stale-lock timeout yok, PID/timestamp yok |
| Idempotency store | `src/orchestrator/idempotency.py` | `path.write_text()` | Deterministic run_id (SHA256) | Atomik degil; concurrent write korumasiz |
| Work item leases | `src/ops/work_item_leases.py` | load → modify → save | Stale lease cleanup mevcut | Read-modify-write atomik degil; race condition |
| Doer loop lock | `src/ops/doer_loop_lock.py` | write + stale detect | Stale-lock temizleme + kanit yazimi | Temizleme ve yazma atomik degil |
| Evidence writer | `src/evidence/writer.py` | append + manifest | SHA256 integrity manifest | Append idempotent degil; resume'da duplicate entry |
| Evidence verify | `src/evidence/integrity_verify.py` | SHA256 recompute | Corruption detection mevcut | Manifest kendisi korumasiz; torn write algilanmaz |

### 1.2 Kritik Bosluklar

1. **Fsync eksikligi**: `write_text_atomic()` ve `write_bytes_atomic()` rename yapar ama `os.fsync()` cagirmaz. Ext4 `data=writeback` modunda rename sonrasi crash → icerik kaybi mumkun.

2. **CAS (Compare-And-Swap) yok**: Tum stateful dosyalar (lease, idempotency, doer lock) load-modify-write pattern kullaniyor. Iki concurrent process ayni dosyayi okuyup yazarsa, son yazan kazanir, onceki degisiklik sessizce kaybolur.

3. **Global file locking yok**: Governor lock sadece runner pipeline icin. Lease dosyalari, idempotency store, evidence yazimlari icin lock mekanizmasi yok.

4. **Corruption detection at rest yok**: State dosyalarinda (lease, idempotency, doer lock) checksum, version, written_at, writer_pid gibi metadata yok. Silent corruption algilanamaz.

5. **Resume idempotency yok**: Evidence `_append_text()` (`writer.py`) crash sonrasi ayni log entry'yi tekrar yazar. Event ID veya dedup mekanizmasi yok.

6. **Stale lock recovery**: Governor lock'ta (`runner_config.py`) timeout yok. Process crash yapip lock dosyasini birakirsa, manuel temizlik gerekir. Doer loop lock'ta stale detect var ama governor'da yok.

### 1.3 Onerilen Cozumler

| # | Oneri | Hedef Dosya | Etki |
|---|-------|-------------|------|
| P0.1 | `write_json_durable()`: atomic write + fsync + verify | `src/shared/atomicity.py` (yeni) | Tum stateful yazimlarin temeli |
| P0.2 | `atomic_modify_json()`: load + modifier callback + CAS + retry | `src/shared/atomicity.py` | Race condition onleme |
| P0.3 | `file_lock()` context manager: `fcntl.flock` wrapper + timeout | `src/shared/atomicity.py` | Concurrent write koruması |
| P0.4 | State `_meta` alani: version, checksum, written_at, writer_pid | Her state JSON dosyasi | Corruption detect + forensics |
| P0.5 | Governor lock'a TTL + PID yazma + stale cleanup | `src/orchestrator/runner_config.py` | Deadlock onleme |
| P0.6 | Evidence append'e event_id + dedup kontrolu | `src/evidence/writer.py` | Resume guvenliği |
| P0.7 | Crash consistency contract dokumani | `docs/OPERATIONS/CRASH-CONSISTENCY-CONTRACT.v1.md` | Per-file tablo: owner, write pattern, atomicity, lock, recovery, corruption detection |

### 1.4 Teknik Backlog — P0

```
P0.1 write_json_durable
  Dosya: src/shared/atomicity.py (yeni modul)
  Degisiklik: tmp file → write → fsync(fd) → rename → fsync(dir_fd) → verify checksum
  Test: tmp dosya olustur, fsync oncesi kill simule et, dosya bozulmamis olmali
  Kabul kriteri: tum write_json_atomic cagrilari write_json_durable'a migrate

P0.2 atomic_modify_json
  Dosya: src/shared/atomicity.py
  Degisiklik: load → file_lock → modify callback → write_json_durable → unlock
  Test: iki thread ayni dosyayi concurrent modify → her iki degisiklik korunmus
  Kabul kriteri: lease ve idempotency store bu fonksiyonu kullaniyor

P0.3 file_lock
  Dosya: src/shared/atomicity.py
  Degisiklik: fcntl.flock(LOCK_EX) + timeout + stale detect (PID check)
  Test: lock alinmisken ikinci acquire → timeout sonrasi fail
  Kabul kriteri: lease, idempotency, evidence yazimlari lock altinda

P0.4 State _meta
  Dosya: Her state JSON (lease, idempotency, governor, doer lock)
  Degisiklik: {"_meta": {"version": "v1", "checksum": "sha256:...", "written_at": "...", "writer_pid": 1234}}
  Test: _meta olmayan dosya yukleme → WARN log; checksum mismatch → FAIL
  Kabul kriteri: tum stateful dosyalar _meta tasiyor

P0.5 Governor TTL + PID
  Dosya: src/orchestrator/runner_config.py
  Degisiklik: lock dosyasina JSON yaz {pid, acquired_at, ttl_seconds}; acquire'da stale check
  Test: stale lock (eski PID, suresi dolmus) → otomatik temizleme ve yeni lock
  Kabul kriteri: crash sonrasi governor lock TTL sonrasi otomatik aciliyor

P0.6 Evidence event dedup
  Dosya: src/evidence/writer.py
  Degisiklik: her append'e event_id (run_id + step + seq); append oncesi son satiri oku, ayni event_id varsa skip
  Test: ayni event_id ile iki kez append → tek entry
  Kabul kriteri: resume sonrasi duplicate log entry yok

P0.7 Crash consistency contract
  Dosya: docs/OPERATIONS/CRASH-CONSISTENCY-CONTRACT.v1.md
  Degisiklik: per-file tablo (stateful dosya, owner modul, write pattern, atomicity level, lock type, recovery mechanism, corruption detection)
  Test: CI gate ile dokuman varligi ve tablo bos olmamasi check
  Kabul kriteri: tum bilinen stateful dosyalar tabloda listelenmis
```

---

## 2. State Machine Consolidation

### 2.1 Mevcut Durum

Iki ayri state modeli birbirinden bagimsiz calisiyor:

| Model | Tanimlayan Dosya | State'ler | Nerede Yasiyor |
|-------|------------------|-----------|----------------|
| Work Item | `src/ops/work_item_state.py` | OPEN, PLANNED, IN_PROGRESS, APPLIED, CLOSED, NOOP | `.cache/index/work_item_state.v1.json` |
| Execution | Inline string (schema'da) | COMPLETED, FAILED, SUSPENDED | `.cache/reports/<run_id>/summary.json` |

Pipeline 6 asamali (Validate → Governor → Routing → Idempotency → Quota/Autonomy → Execute/Finalize) — sirali ve deterministik. Ama state gecisleri valide edilmiyor.

State machine davranisi PROJECT-SSOT'ta tanimli: `OPEN/PLANNED/IN_PROGRESS/APPLIED/CLOSED/NOOP` (satir 44).

### 2.2 Bosluklar

1. **Transition validation yok**: OPEN'dan dogrudan CLOSED'a gecis engellenmiyor. Sadece 2 kural mevcut (close: final state check, reopen: CLOSED check).
2. **Iki model arasi mapping yok**: Execution COMPLETED → Work Item APPLIED gecisi implicit ve garanti altinda degil.
3. **Work item state icin JSON schema yok**: State'ler Python constant olarak tanimli ama schema ile valide edilmiyor.
4. **`orchestrator/state_machine.v1.json` placeholder**: `"note": "Placeholder. Extend to real execution state machine later."` — gercek state grafi yok.
5. **Forward-only constraint yok**: Reopen haric, herhangi bir state'e geri donulebilir (kural yok).
6. **Contract test yetersiz**: `single_trace_state_machine_contract_test.py` presence check yapiyor, gecis sirasi check degil.

### 2.3 Onerilen Cozumler

| # | Oneri | Hedef | Etki |
|---|-------|-------|------|
| S.1 | `schemas/state-machine-work-item.schema.v1.json` | Transition matrix | Gecerli gecisleri schema ile enforce |
| S.2 | `orchestrator/state_machine.v1.json` doldurma | Gercek state grafi | Placeholder'i canli SSOT yap |
| S.3 | `validate_transition()` | `src/ops/work_item_state.py` | Invalid gecisleri engelle |
| S.4 | Execution → Work Item mapping | Bridge modul | Iki model arasi tutarlilik |
| S.5 | Execution state constants | `src/orchestrator/constants.py` | Inline string'leri kaldir |
| S.6 | Trajectory contract test | `tests/` | Full OPEN→APPLIED yolunu test et |

### 2.4 Teknik Backlog — State

```
S.1 Transition matrix schema
  Dosya: schemas/state-machine-work-item.schema.v1.json (yeni)
  Degisiklik: {transitions: [{from: "OPEN", to: ["PLANNED", "NOOP", "CLOSED"]}, ...]}
  Test: validate_schemas.py gecmeli
  Kabul kriteri: gecersiz gecis (orn. NOOP→OPEN) schema fail uretir

S.2 state_machine.v1.json doldurma
  Dosya: orchestrator/state_machine.v1.json
  Degisiklik: placeholder → {version, states: [...], transitions: [...], final_states: [...]}
  Test: validate_schemas.py; work_item_state.py'deki constant'larla match
  Kabul kriteri: dokuman ve kod ayni state/transition setini kullaniyor

S.3 validate_transition()
  Dosya: src/ops/work_item_state.py
  Degisiklik: update_state() icinde gecis oncesi transition matrix'e bakma
  Test: OPEN→APPLIED gecisi → ValidationError
  Kabul kriteri: tum state degisiklikleri validate_transition'dan geciyor

S.4 Execution → Work Item bridge
  Dosya: src/ops/ veya src/orchestrator/ (yeni veya mevcut)
  Degisiklik: COMPLETED→APPLIED, FAILED→(state kalir), SUSPENDED→IN_PROGRESS mapping
  Test: execution COMPLETED sonrasi work item APPLIED'a gecmis olmali
  Kabul kriteri: iki model arasi mapping explicit ve test edilmis

S.5 Execution state constants
  Dosya: src/orchestrator/constants.py (yeni)
  Degisiklik: RESULT_COMPLETED = "COMPLETED", RESULT_FAILED = "FAILED", RESULT_SUSPENDED = "SUSPENDED"
  Test: Python kaynak dosyalarinda (src/**/*.py) literal "COMPLETED"/"FAILED"/"SUSPENDED" kullanimi → constants import'undan gelmeli
  Kabul kriteri: src/ altindaki .py dosyalarinda constants.py disinda literal result_state string kullanimi yok (snapshot, fixture, dokuman ve test assertion'lar haric)

S.6 Trajectory contract test
  Dosya: tests/ops/test_state_machine_trajectory.py (yeni)
  Degisiklik: OPEN→PLANNED→IN_PROGRESS→APPLIED full trajectory test
  Test: pytest tests/ -x
  Kabul kriteri: OPEN→APPLIED (invalid skip) → test fail
```

---

## 3. Decision Policy Engine

### 3.1 Mevcut Durum

- `orchestrator/decision_policy.v1.json`: `approval_risk_threshold: 0.7`
- `src/orchestrator/decision_boundary.py` (97 LOC): full_auto / human_review / strict_deny resolution
- `src/ops/decision_inbox.py`: karar toplama + safe default uygulama
- `docs/OPERATIONS/DECISION-POLICY.md`: Safe defaults (NETWORK=OFF, AUTO_APPLY=BLOCKED) + insan onayi gerektiren kararlar dokumante edilmis

Threshold + 3-tier boundary calisiyor. Decision Inbox mevcut ve fonksiyonel.

### 3.2 Bosluklar

1. **Rule composition yok**: Kararlar if/else zinciri; declarative kural motoru yok.
2. **Audit trail eksik**: Hangi kuralin hangi sonucu urettigini izleyen structured log yok.
3. **Decision reversibility yok**: Uygulanan karar geri alinamiyor.
4. **Risk scoring basit**: `risk_score` tek scalar; multi-factor scoring (blast radius, reversibility, confidence) yok.

### 3.3 Onerilen Cozumler (P3 — gelecek iterasyon)

| # | Oneri | Etki |
|---|-------|------|
| D.1 | Declarative rule engine: JSON rule definitions → evaluation | Extensible karar mekanizmasi |
| D.2 | Decision audit log: her karar icin structured trace | Compliance + debugging |
| D.3 | Decision rollback: applied karar geri alma mekanizmasi | Safety net |
| D.4 | Multi-factor risk scoring: blast_radius, reversibility, confidence | Daha nuansli karar siniri |

---

## 4. Test & CI Olgunlugu

### 4.1 Mevcut Durum

| Katman | Sayi | Kapsam | Not |
|--------|------|--------|-----|
| Schema validation | 168 schema | Kapsamli | `validate_schemas.py` tum schema'lari dogruluyor |
| Policy dry-run | 31 fixture | Kapsamli | `policy_dry_run.py` tum fixture'larda calisir |
| Extension contract tests | 50 dosya | Tam | Her extension'da en az 1 contract test |
| Inline contract tests | 316 dosya | Yaygin ama daginik | `src/` ve `ci/` icinde `*_contract_test.py` |
| Command modules | 37 modul | — | 156 registered subcommand |
| Command-level tests | 5 test | Cok zayif | 156 subcommand'dan 5'i test edilmis |
| Integration tests | 0 | Yok | Cross-command workflow testi yok |
| Performance tests | 0 | Yok | Latency baseline yok |

### 4.2 Bosluklar

1. **Command-level test coverage zayif**: 156 registered subcommand'dan 5'i command-seviyesinde test edilmis. 316 inline contract test var ama pytest disinda ve daginik.
2. **conftest.py yok**: Her test kendi fixture setup'ini yapiyor; tekrar ve tutarsizlik.
3. **Dual-mode fragmentation**: pytest + standalone `__main__` script karisimi.
4. **Parametrize kullanilmiyor**: Test varyasyonlari copy-paste.
5. **Integration test yok**: intake → plan → execute → evidence zinciri test edilmemis.

### 4.3 Onerilen Cozumler

| # | Oneri | Etki |
|---|-------|------|
| T.1 | `tests/conftest.py`: ortak fixture'lar (workspace, repo_root, sample_envelope) | Duplicate azaltma |
| T.2 | Kritik ops komut testleri: system-status, work-intake-check, deploy-check | Coverage artisi |
| T.3 | Integration test suite: intake→plan→execute→evidence→verify | End-to-end guven |
| T.4 | Standalone testleri pytest'e migrate (P2) | Tutarlilik |

### 4.4 Teknik Backlog — Test

```
T.1 conftest.py
  Dosya: tests/conftest.py (yeni)
  Degisiklik: workspace_root, repo_root, sample_envelope, mock_policy fixture'lari
  Test: mevcut testler hala geciyor (pytest tests/ -x)
  Kabul kriteri: yeni testler conftest fixture kullaniyor

T.2 Kritik komut testleri
  Dosya: tests/ops/test_system_status.py, test_work_intake_check.py, test_deploy_check.py (yeni)
  Degisiklik: her biri tmp_path workspace ile basic contract test
  Test: pytest tests/ -x
  Kabul kriteri: command-level test sayisi 5→8+

T.3 Integration test
  Dosya: tests/integration/test_intake_to_evidence.py (yeni)
  Degisiklik: work-intake-check → planner-show-plan → (simulate exec) → evidence verify
  Test: pytest tests/integration/ -x
  Kabul kriteri: zincir basariyla tamamlaniyor, evidence dosyalari mevcut ve integrity OK
```

---

## 5. Execution Core — Parcalilik

### 5.1 Mevcut Durum

`src/orchestrator/` = 6,697 LOC production (7,773 LOC testler dahil).
6 asamali pipeline calisiyor: Validate → Governor → Routing → Idempotency → Quota/Autonomy → Execute/Finalize.

### 5.2 Bosluklar

1. **workflow_exec_steps.py 1,279 LOC**: Script budget soft limit (1,200) asilmis; hard limit (2,000) yaklasiyor. Tek dosyada module dispatch + tool gateway + suspension + budget checkpoint.
2. **Resume kopuklugu**: `runner_resume.py` (385 LOC) pipeline stage'lerinden bagimsiz calisiyor.
3. **Strategy table dar**: 5 route; extension-based routing yok.
4. **State bridge yok**: RunContext (memory) ↔ work_item_state (disk) ↔ evidence/summary (disk) arasi explicit mapping yok.

### 5.3 Onerilen Cozumler (P2 — depth & discipline)

| # | Oneri | Etki |
|---|-------|------|
| E.1 | `workflow_exec_steps.py` parcalama: module_dispatch.py, tool_gateway.py, budget_checkpoint.py | Script budget uyumu + okunurluk |
| E.2 | Resume logic'i pipeline stage olarak entegre | Tutarli execution flow |
| E.3 | Strategy table'i extension manifest'lerden otomatik uret | Route coverage artisi |
| E.4 | State bridge modulu: RunContext ↔ work_item_state ↔ evidence | Tek state gorunumu |

---

## 6. Uygulama Sirasi

```
Faz 1 (P0): Crash Safety Foundation
  P0.1 → P0.3 → P0.4 → P0.5 → P0.7
  Tahmini kapsam: 1 yeni modul + 4-6 dosya degisikligi + 1 dokuman

Faz 2 (State): Consolidation
  S.1 → S.2 → S.3 → S.5 → S.6
  Tahmini kapsam: 1 yeni schema + 5-6 dosya degisikligi + 1 test

Faz 3 (Test): Coverage
  T.1 → T.2 → T.3
  Tahmini kapsam: 5-8 yeni test dosyasi

Faz 4 (Execution): Refactoring — P2
  E.1 → E.4 → E.2
  Tahmini kapsam: 5-8 dosya degisikligi

Faz 5 (Decision): Engine — P3
  D.1 → D.2
  Gelecek iterasyon
```

---

## Referanslar

Tum dosya referanslari 2026-03-26 tarihinde repo icinde dogrulanmistir:
- `src/shared/utils.py` (116 LOC)
- `src/orchestrator/runner_config.py` (225 LOC)
- `src/orchestrator/idempotency.py` (79 LOC)
- `src/ops/work_item_leases.py` (143 LOC)
- `src/ops/doer_loop_lock.py` (190 LOC)
- `src/evidence/writer.py` (182 LOC)
- `src/evidence/integrity_verify.py` (103 LOC)
- `src/ops/work_item_state.py` (151 LOC)
- `src/orchestrator/decision_boundary.py` (97 LOC)
- `src/orchestrator/quality_gate.py` (142 LOC)
- `src/orchestrator/workflow_exec_steps.py` (1,279 LOC)
- `src/orchestrator/runner_resume.py` (385 LOC)
- `src/orchestrator/runner_execute.py` (80 LOC)
- `orchestrator/state_machine.v1.json` (placeholder)
- `orchestrator/decision_policy.v1.json` (approval_risk_threshold: 0.7)
- `orchestrator/strategy_table.v1.json` (5 route)
- `docs/OPERATIONS/PROJECT-SSOT.md` (state machine tanimi, satir 44)
- `docs/OPERATIONS/DECISION-POLICY.md` (decision kuralları)

# IMPROVEMENT-ANALYSIS (v1)

**Amac**

Bu rapor, `autonomous-orchestrator` repo'sunun iyilestirme alanlarini implementasyon karari oncesinde tek yerde toplamak icin hazirlandi.

Temel gozlem:

- Governance / schema / policy / layer-boundary taraflari olgun.
- Execution core calisiyor, ancak state, locking, recovery ve route kapsami acisindan parcali gorunuyor.
- Crash safety mevcut ama lokal korumalarla sinirli.
- Test hacmi yuksek olsa da dagilim dengesiz; ozellikle command-level ve end-to-end zincirlerde bosluk var.

Not:

- Bu rapor analiz ve oneridir; kod degisikligi uygulamaz.
- Oncelik sirasi kullanici baglaminda verilen `P0 -> P3` dizilimine gore ele alindi.

## 1. P0 - Crash Consistency & Data Integrity

### Mevcut Durum

| Bilesken | Dosya | Mekanizma | Guclu | Zayif |
|---|---|---|---|---|
| Atomic write helper | `src/shared/utils.py:37-60` | tmp -> rename | Basit ve tekrar kullanilabilir atomik yazim deseni var | `fsync` yok; crash aninda kernel buffer flush edilmeden veri kaybi riski suruyor |
| JSON save helper | `src/utils/jsonio.py:12-16` | `path.write_text()` | Kullanim kolay, sade API | Atomik degil; evidence ve orchestrator tarafinda dogrudan kullaniliyor |
| Governor lock | `src/orchestrator/runner_config.py:64-93` | `O_CREAT | O_EXCL` | Ayni anda ikinci runner'i kaba seviyede engelliyor | TTL yok, PID yok, stale-lock recovery yok |
| Idempotency store | `src/orchestrator/idempotency.py:57-60` | load/save JSON map | Deterministic run-id ve mapping mantigi var | Yazim atomik degil; concurrent writer korumasi yok |
| Work item leases | `src/ops/work_item_leases.py:81-137` | load -> modify -> save | Stale lease cleanup var | Read-modify-write atomik degil; race condition acik |
| Doer loop lock | `src/ops/doer_loop_lock.py:101-176` | load / stale detect / rewrite | Stale lock temizleme mantigi var | Temizleme ve yeniden yazma ayri adimlar; global file lock yok |
| Work item state | `src/ops/work_item_state.py:94-151` | state JSON + JSONL append | Tek work-item izi olusturuyor | JSON save atomik degil; JSONL append idempotent degil |
| Evidence writer | `src/evidence/writer.py:35-43`, `src/evidence/writer.py:94-182` | append + JSON save + integrity manifest | SHA256 manifest ile sonradan verify edilebiliyor | `_append_text()` / `_append_jsonl()` duplicate event uretebilir; `save_json()` atomik degil |
| Evidence verify | `src/evidence/integrity_verify.py:26-83` | SHA256 recompute | Corruption tespiti var | Manifest dosyasinin kendisi icin durable write / self-protection yok; torn write durumunda yalniz shape invalid donuyor |
| Path write arbitration | `src/orchestrator/file_write_arbitration.py:68-132` | logical lease | Ayni hedef yol icin lease mantigi var | Kayitlar `path.write_text()` ile yaziliyor; OS-level lock / CAS yok |

### Kritik Bosluklar

- `fsync` eksikligi: `write_text_atomic()` rename yapiyor ama dosya veya parent directory `fsync` cagirmiyor. Ani crash / power loss senaryosunda rename oncesi veya sonrasi veri kaybi olasiligi suruyor.
- CAS (Compare-And-Swap) yok: lease, idempotency, work-item-state ve benzeri state dosyalari load-modify-save deseniyle calisiyor. Son yazan kazanir; onceki update sessizce ezilebilir.
- Global file locking yok: governor lock var ama lease, idempotency, evidence ve state store katmanlarinda ortak bir lock primitive yok.
- Corruption metadata zayif: state JSON dosyalarinda `writer_pid`, `checksum`, `revision`, `previous_hash` gibi alanlar yok. Sonradan adli inceleme zorlasiyor.
- JSON save standardi daginik: `src/shared/utils.py` icinde atomik helper varken `src/utils/jsonio.py` ve bazi ops modulleri halen dogrudan `write_text()` kullaniyor.
- Resume idempotency sinirli: evidence append fonksiyonlari event-id veya dedup anahtari kullanmiyor. Resume / retry sonrasi duplicate satirlar olusabilir.
- Governor stale recovery eksik: `acquire_governor_lock()` lock varligina bakiyor ama stale sayma mantigi yok. Crash sonrasi manuel temizleme gerekebilir.

### Onerilen Cozumler

| Oneri | Dosya | Etki |
|---|---|---|
| P0.1 `write_json_durable()` ve `write_text_durable()` eklenmesi: temp file + flush + `os.fsync()` + `replace()` + parent dir fsync | `src/shared/atomicity.py` (yeni) | Tum stateful yazimlar icin ortak durable temel |
| P0.2 `atomic_modify_json()` yardimcisi: load + modify callback + revision/CAS + retry | `src/shared/atomicity.py` (yeni) | Race condition azaltma, lost update onleme |
| P0.3 `file_lock()` context manager: `fcntl.flock` wrapper | `src/shared/atomicity.py` (yeni) | Lease, idempotency ve state yazimlarina process-level koruma |
| P0.4 Stateful JSON'lara `_meta` alani: `revision`, `checksum`, `written_at`, `writer_pid`, `writer_tag` | `work_item_state`, `work_item_leases`, `idempotency`, `doer_loop_lock`, benzeri JSON store'lar | Corruption detect + forensics |
| P0.5 Governor lock'a TTL, PID ve stale cleanup eklemek | `src/orchestrator/runner_config.py` | Deadlock / orphan lock riskini azaltma |
| P0.6 Evidence append'lerine `event_id` ve dedup mantigi eklemek | `src/evidence/writer.py` | Resume guvenligi ve append idempotency |
| P0.7 Crash consistency contract / matris dokumani olusturmak: owner, pattern, atomicity, lock, recovery | `docs/OPERATIONS/CRASH-CONSISTENCY-MATRIX.v1.md` (yeni) | Hangi dosyanin hangi garantiye sahip oldugunu SSOT seviyesinde gorunur kilma |

### Degerlendirme

P0 alaninda repo sifirdan baslamiyor; aksine atomik rename, stale lease ve integrity verify gibi iyi ilk adimlar var. Sorun, bu korumalarin ortak bir transactional model olusturmamasi. Bu nedenle bir sonraki mimari adim "yeni locklar eklemek" degil, tum stateful IO davranisini ayni durable / locked helper altyapisina toplamak olmali.

## 2. State Machine Consolidation

### Mevcut Durum

Bugun iki farkli state modeli var:

| Model | Tanimlayan | States | Nerede Yasiyor |
|---|---|---|---|
| Work Item | `src/ops/work_item_state.py:8-15` | `OPEN`, `PLANNED`, `IN_PROGRESS`, `APPLIED`, `CLOSED`, `NOOP` | `.cache/index/work_item_state.v1.json` ve `.cache/index/work_item_runs.v1.jsonl` |
| Execution / Node / Run | `src/orchestrator/workflow_exec_contracts.py:22-25`, `src/orchestrator/runner_stages/*`, `src/orchestrator/workflow_exec_steps.py` | `COMPLETED`, `FAILED`, `SUSPENDED`, `SKIPPED`, ayrica summary seviyesinde `BLOCKED` | `summary.json`, runner stage snapshot'lari ve in-memory `RunContext` |

Ek gozlemler:

- Pipeline 6 asamali ve deterministik: Validate -> Governor -> Routing -> Idempotency -> Quota/Autonomy -> Execute/Finalize.
- `orchestrator/state_machine.v1.json` halen placeholder: `Placeholder. Extend to real execution state machine later.`
- Work item state update'leri `src/ops/work_intake_exec_ticket.py:912-929` ve `src/ops/work_intake_exec_ticket.py:1052-1069` icinde execution sonuclarindan turetiliyor; bu bridge mevcut ama implicit.

### Kritik Bosluklar

- Transition validation yok: `src/ops/work_item_state.py:94-125` icindeki `update_state()` gelen state'i dogrudan yaziyor. Gecis matrisi enforce edilmiyor.
- Iki model arasi mapping implicit: execution sonucu `APPLIED` / `PLANNED` / `NOOP` gibi work-item state'lerine ayrik if/else ile cevriliyor; tek merkezi bridge yok.
- Schema yok: `schemas/` altinda work item state veya transition matrix icin dedike bir schema bulunmadi.
- `orchestrator/state_machine.v1.json` placeholder durumda; canli SSOT gorevi gormuyor.
- Forward-only constraint yok: `OPEN -> CLOSED` gibi gecisleri kod seviyesi guard ile engelleyen bir mekanizma gorunmuyor.
- Contract test sinirli: `src/ops/single_trace_state_machine_contract_test.py` state dosyasi ve bazi durumlarin varligini kontrol ediyor; tam trajectory order validate etmiyor.
- Execution status'leri inline string: `COMPLETED`, `FAILED`, `SUSPENDED` gibi degerler farkli dosyalarda literal olarak kullaniliyor; ortak constants katmani yok.

### Onerilen Cozumler

| Oneri | Dosya | Etki |
|---|---|---|
| S.1 Work item transition matrix schema'si eklemek | `schemas/state-machine-work-item.schema.v1.json` (yeni) | Gecerli gecisleri schema seviyesinde tanimlama |
| S.2 Placeholder state machine dosyasini gercek graf ile doldurmak | `orchestrator/state_machine.v1.json` | SSOT state grafi |
| S.3 `validate_transition()` fonksiyonu eklemek | `src/ops/work_item_state.py` | Invalid gecisleri yazim oncesi engelleme |
| S.4 Execution -> Work Item mapping icin explicit bridge modulu yazmak | `src/orchestrator/state_bridge.py` veya `src/ops/state_bridge.py` (yeni) | Iki model arasi tutarlilik |
| S.5 Execution status constants dosyasi eklemek | `src/orchestrator/constants.py` (yeni) | Inline string daginikligini azaltma |
| S.6 Full trajectory contract testleri eklemek | `src/ops/` veya `tests/` altinda yeni testler | `OPEN -> PLANNED -> IN_PROGRESS -> APPLIED/CLOSED/NOOP` yolunu ve invalid transition'lari dogrulama |

### Degerlendirme

Buradaki sorun "hic state machine yok" degil; state machine'in SSOT, code-path ve evidence katmanlarina esit yayilmamis olmasi. Dogru hedef yeni state sayilari icat etmek degil, mevcut iki state modelini tek mapping kontratina oturtmak.

## 3. Decision Policy Engine

### Mevcut Durum

Repo'da karar altyapisi mevcut:

- `orchestrator/decision_policy.v1.json:1-5`: su an yalnizca `approval_risk_threshold: 0.7` ve "extend later" notu iceriyor.
- `src/orchestrator/decision_boundary.py` (97 LOC): `full_auto`, `human_review`, `strict_deny` resolution.
- `src/ops/decision_inbox.py` (948 LOC): seed, inbox, apply ve `decisions_applied.v1.jsonl` uretimi.
- `docs/OPERATIONS/DECISION-POLICY.md`: safe defaults, insan onayi gerektiren aksiyonlar ve status semantigi.
- `src/orchestrator/runner_config.py` ve ilgili runner stage'ler: autonomy/threshold baglami.

Bugunku model calisiyor, ancak agirlikla su eksende:

- threshold / boundary resolution
- safe default apply
- decision inbox kaydi

### Bosluklar

- Rule composition sinirli: karar davranisi declarative bir kural motorundan cok kod icindeki if/else ve threshold semantigine dayaniyor.
- Audit trail var ama rule-trace yok: `decisions_applied.v1.jsonl` bulunuyor, fakat "hangi kural / hangi kosul / hangi override bu sonuca yol acti" seviyesinde detayli trace standardi yok.
- Rollback semantigi net degil: uygulanan kararlar icin explicit geri alma veya supersede mekanizmasi belirgin degil.
- Risk scoring tek-boyutlu: `risk_score` tek scalar olarak kullaniliyor; actor, target, side-effect tipi, environment, confidence gibi faktorler ayri bir kompozisyon modeliyle ifade edilmiyor.
- Decision intent ve execution outcome baglantisi daginik: karar sonucu ile pipeline stage sonucu arasinda tek normalized audit modeli yok.

### Onerilen Cozumler (P3 - sonraki iterasyon)

| Oneri | Etki |
|---|---|
| D.1 Declarative rule engine: JSON rule definitions -> evaluator | Extensible karar modeli |
| D.2 Decision audit trace: rule_id, matched_conditions, winning_rule, overridden_by, resulting_action | Compliance ve debugging derinligi |
| D.3 Decision rollback / supersede mekanizmasi | Yanlis auto-apply kararlarini geri alma guvencesi |
| D.4 Multi-factor risk scoring | Daha nuansli karar siniri |

### Degerlendirme

Bu alan temel olarak yok degil; tersine repo'nun olgun governance taraflarindan biri. Ancak bugunku haliyle "policy engine" degil, daha cok "boundary + inbox + safe default" kombinasyonu. Bu nedenle P3 olarak konumlanmasi mantikli.

## 4. Test & CI Olgunlugu

### Mevcut Durum

Repo'da test hacmi yuksek, ancak dagilim esit degil. Fiili repo durumu su sekilde ozetlenebilir:

| Katman | Test Sayisi / Hacim | Kapsam | Notlar |
|---|---|---|---|
| Schema validation | 168 schema | Kapsamli | `ci/validate_schemas.py` guncel ciktiyla 168 schema dogruluyor |
| Policy dry-run | 31 fixture | Kapsamli | `ci/policy_dry_run.py` `fixtures/envelopes` altinda 31 fixture calistiriyor |
| Extension manifest / extension contract | 50 test dosyasi | Guclu | Extension yuzeyinde belirgin contract test yogunlugu var |
| Ops commands | 5 command-seviyesi contract test, 37 command modulu, 156 ust-seviye subcommand | Zayif | Command surface genis, dogrudan command-test yogunlugu dusuk |
| Inline contract tests | 316 dosya (`src + ci`), 297 dosya (`src`) | Yaygin ama daginik | `*_contract_test.py` yapisi genis ama merkezi degil |
| Bootstrap | `ci/context_bootstrap_contract_test.py` mevcut | Kismi | Tier 1/2/3 zinciri icin tam sayisal coverage matrisi yok |
| Integration | Belirgin tek zincir suite'i yok | Zayif | Cross-command workflow testi sinirli |
| Performance | Belirgin latency baseline suite'i yok | Zayif | Sistematik performans regresyon kapi gozlenmiyor |

Ek notlar:

- Repo icinde uygulama koduna ait bir `conftest.py` bulunmadi; yalnizca `.venv` altinda ucuncu parti paket `conftest.py` dosyalari var.
- Test yogunlugu extension ve contract tarafinda yuksek; command surface ve end-to-end zincirde dusuk.

### Kritik Bosluklar

- Test sayisi fazla ama command coverage daginik: extension ve contract odagi guclu, command-package odagi zayif.
- `conftest.py` eksikligi nedeniyle ortak fixture dili zayif; test setup'lari tekrara acik.
- Standalone script test + contract test + CI script karisimi var; bu durum test ergonomisini ve yeni katkiyi zorlastiriyor.
- Parametrize ve shared builders kulturu zayif gorunuyor; ayni patern farkli dosyalarda tekrar ediyor.
- End-to-end zincir guvencesi eksik: work intake secimi, execution, evidence yazimi, integrity verify ve status surfacing tek senaryoda birlikte dogrulanmiyor.

### Onerilen Cozumler

| Oneri | Etki |
|---|---|
| T.1 Repo-seviyesi `tests/conftest.py` ve ortak fixture seti | Duplicate azaltma, test yazma hizi |
| T.2 Kritik command'lar icin yeni contract testler: `system-status`, `work-intake-check`, `deploy-check`, `airunner-run`, `release-check` | Komut yuzeyi guveni |
| T.3 Entegre zincir test suite'i: intake -> select -> execute -> evidence -> verify -> status | End-to-end guvence |
| T.4 Standalone script testlerini kademeli olarak pytest pattern'ine yaklastirmak | Tutarlilik ve okunurluk |
| T.5 Test envanteri ve coverage matrisi dokumani | Hangi alanin ne kadar korundugunu gorunur kilma |

### Degerlendirme

Buradaki ana sorun "test yok" degil, "dogru yerde test yogunlugu yok". Repo bugun governance ve extension kontratlarini iyi testliyor; bundan sonraki kazanc execution zinciri ve command surface testlerinden gelecek.

## 5. Execution Core - Parcalilik Analizi

### Mevcut Durum

`src/orchestrator/` altindaki execution yapisi calisiyor, ancak tek bir "motor" hissi vermekten cok birden fazla modulin koordinasyonuna dayaniyor.

Gozlemler:

- `src/orchestrator/` toplaminda yaklasik 6,697 LOC production kod, test dosyalariyla birlikte 7,773 LOC bulunuyor.
- `src/orchestrator/workflow_exec_steps.py` su an 1,279 LOC.
- `src/orchestrator/runner_resume.py` 385 LOC ve ana pipeline'dan kavramsal olarak ayrik duruyor.
- `orchestrator/strategy_table.v1.json` su an 5 route iceriyor.
- Routing, idempotency, quota/autonomy, execute/finalize asamalari pipeline icinde var; fakat state gorunumu RunContext, work-item-state ve evidence summary arasinda dagiliyor.

### Kritik Bosluklar

- `workflow_exec_steps.py` soft script-budget sinirini asiyor; tek dosyada cok fazla sorumluluk tasiyor.
- Module dispatch, tool gateway, suspension handling, budget checkpoint ve node result normalization ayni dosyada ic ice.
- Resume logic pipeline stage'lerinden ayrik hissettiriyor; kavramsal akista ikinci bir execution yolu olusturuyor.
- Strategy table statik ve dar kapsamli; extension manifest tabanli route uretimi gorulmuyor.
- State bridge eksik: RunContext, `work_item_state.v1.json` ve evidence `summary.json` arasinda tek normalize "execution state view" yok.

### Onerilen Cozumler (P2 - depth & discipline)

| Oneri | Etki |
|---|---|
| E.1 `workflow_exec_steps.py` parcalama: `module_dispatch`, `tool_gateway`, `budget_checkpoint`, `decision_gate`, `result_normalizer` | Script budget uyumu + okunurluk |
| E.2 Resume logic'i ayrik yardimci olmaktan cikarip pipeline stage olarak konumlamak | Tek execution flow |
| E.3 Strategy table'i extension manifest / registry kaynaklarindan generate etmek | Route coverage ve maintainability |
| E.4 State bridge modulu: `RunContext <-> work_item_state <-> evidence summary` | Tek state gorunumu |

### Degerlendirme

Execution core'un sorunu "calismiyor" degil; artik governance olgunlugunu tasiyacak kadar merkezilesmemis olmasi. Bu nedenle P2 refaktorleri dogrudan yeni capability eklemekten daha degerli olabilir.

### Uygulama Sirasi Onerisi

### Faz 1 - Crash Safety Foundation (P0)

Onerilen sira:

1. P0.1 durable write primitive
2. P0.3 file lock primitive
3. P0.2 atomic modify / CAS wrapper
4. P0.4 state metadata standardi
5. P0.5 governor stale recovery
6. P0.6 evidence dedup
7. P0.7 crash consistency matrisi

Beklenen etki:

- Tum stateful IO icin ortak primitive
- Orphan lock ve lost update riskinde dogrudan azalma
- Sonraki state-machine consolidation icin daha saglam zemin

### Faz 2 - State Consolidation

Onerilen sira:

1. S.1 work-item transition schema
2. S.2 canonical state machine JSON
3. S.3 transition validation
4. S.5 execution constants
5. S.4 explicit bridge
6. S.6 trajectory contract tests

Beklenen etki:

- Transition'lar dokuman + schema + code seviyesinde teklesir
- Work item ve execution state gorunumleri uyumlu hale gelir

### Faz 3 - Test Coverage

Onerilen sira:

1. T.1 shared fixtures
2. T.2 command-level contract tests
3. T.3 end-to-end zincir testleri
4. T.4 test standardizasyonu

Beklenen etki:

- Execution ve command surface guveni artar
- Refaktor riskleri kontrol altina alinir

### Faz 4 - Execution Refactoring

Onerilen sira:

1. E.1 `workflow_exec_steps.py` parcalama
2. E.4 state bridge
3. E.2 resume integration
4. E.3 strategy generation

Beklenen etki:

- Core daha az parcali gorunur
- Yeni route ve extension eklemek daha ucuz hale gelir

### Faz 5 - Decision Engine (P3)

Onerilen sira:

1. D.1 declarative rule engine
2. D.2 structured audit trace
3. D.3 rollback / supersede
4. D.4 multi-factor risk scoring

Beklenen etki:

- Decision tarafi threshold merkezli olmaktan cikarak policy engine olgunluguna yaklasir

### Dogrulama

- Rapor, repo icinde dogrulanan gercek dosya yollarina dayandirildi.
- Bu calismada analiz dokumani disinda uygulama kodu degistirilmedi.
- P0-P3 onceligi kullanici baglaminda verilen siralamaya gore korundu.

### Sonuc

Repo'nun mevcut gucu governance, schema/policy, extension kontrati ve fail-closed disiplininden geliyor. Iyilestirme yol haritasi bu gucu bozmayip execution tarafina tasimali.

Bu nedenle en saglikli strateji:

- once crash safety ve state durability temeli,
- sonra state machine konsolidasyonu,
- ardindan test coverage,
- en son execution refaktorleri ve gelismis decision engine.

Boylece repo "guclu governance + parcali execution" durumundan "guclu governance + toplu ve guvenilir execution core" durumuna evrilebilir.

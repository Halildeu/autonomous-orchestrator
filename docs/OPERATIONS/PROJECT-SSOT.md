# PROJECT-SSOT (Kalici) — Tam Otomatik + No-Wait + Decision-First

## Amac
Bu repo'nun isletim sistemi: **tam otomatik**, **no-wait job+poll**, **decision-first**, **extension-as-model**.

## Temel davranis
- Tek kapi (program-led): kullanici shell komutu yazmaz; ops komutlari calisir ve kanit uretir.
- No-wait: uzun isler **job-start ile baslar**, sonraki tick'te **poll** ile guncellenir.
- Decision-first: riskli/geri donussuz adimlar **Decision Inbox**'a duser; onaydan sonra yurur.
- Network varsayilan kapalidir; policy/decision ile acilir.

## Katmanlar
- L0 CORE: motor + kapilar + dogrulamalar (kilitli, kontrollu yazim)
- L1 CATALOG: kalici kurallar/format/policy/packs
- L2 WORKSPACE: raporlar, kanitlar, override'lar, job index'ler, intake/decisions
- L3 EXTERNAL: musteri/proje ciktilari (dis repo / teslim)

## Deploy yaklasimi (bu proje)
- Front: statik saglayici (Netlify vb.)
- Backend: kendi hosting / kendi pipeline
- Deploy akisi **PRJ-DEPLOY** extension'i ile yonetilir; no-wait deploy job kayitlari workspace'te tutulur.

## Extension yaklasimi
- Extension = tekrar kullanilabilir "model paketi": schema+policy+ops+intake+cockpit+test
- Ayni extension hem bizde hem musteri repo'larinda calisabilir (portability).
- Her extension job/poll ve decision-gated prensiplerine uyumlu olmali.

## Entegrasyon / Uyum
- Entegrasyon/uyum core refleksidir; yeni lens icat edilmez, alias olarak kullanilir.
- Kanit zinciri: raw -> eval -> gap -> pdca (core davranis).
- Lens referansi: `integrity_compat` (North Star eval).
- Degerlendirme cikti: `.cache/ws_customer_default/.cache/index/assessment_eval.v1.json`
- Cockpit yansimasi: `.cache/ws_customer_default/.cache/reports/system_status.v1.json` (benchmark)
- Uyum bozulursa gap -> work_intake -> decision zinciri calisir.
- Pack/layer checks: layer boundary + pack validation kapilari.

## Tek Iz / Tek Is Kurali
- Her is (work_item) tek bir work_item_id ile izlenir; ayni is tekrar baslatilmaz.
- Her run deterministik run_id uretir (is+plan+policy girdilerine bagli).
- Per-item lease: aktif lease varken yeni calistirma SKIP/LOCKED_ITEM olur.
- Lease stale ise temizlenir; yeni lease alinir (kanit yazilir).
- trace_meta: run_id + work_item_id + evidence_paths raporlarda bulunur.
- run_fingerprint: plan_hash + inputs_hash + policy_hash (idempotency referansi).
- State machine: OPEN/PLANNED/IN_PROGRESS/APPLIED/CLOSED/NOOP.

## One-shot src allowlist window
- src/** yazimi varsayilan olarak KAPALIDIR (core lock).
- Istisna: policy_core_immutability one_shot_src_window ile tek seferlik pencere acilir.
- Pencere: allow_paths + ttl_seconds + opened_at/expires_at + reason zorunludur.
- CORE_UNLOCK + CORE_UNLOCK_REASON + compliance evidence olmadan pencere acilmaz.
- Pencere bitince restore_policy_hash ile geri yukleme ve kanit zorunludur.
- Sadece CHG'de listelenen path'ler yazilabilir; baska src yazimi BLOCKED.

## Calisma saatleri / override mantigi
- "Calisma saatleri" mekanizmasi policy'de tanimlidir.
- Bugune ozel saat (orn. 17:00) **kalici dosyada yazilmaz**.
- Gunluk degerler RUN-CARD ile tutulur: `docs/OPERATIONS/RUN-CARD-TEMPLATE.md`
- Gunluk degerler: workspace override + run-card olarak tutulur:
  - workspace override: `.cache/ws_customer_default/.cache/policy_overrides/*.override*.json`
  - run-card kaniti: `.cache/ws_customer_default/.cache/reports/RUN-CARD-YYYYMMDD.md`

## Kanit / nereden bakarim?
- Durum: `.cache/ws_customer_default/.cache/reports/system_status.v1.json`
- UI snapshot: `.cache/ws_customer_default/.cache/reports/ui_snapshot_bundle.v1.json`
- Intake: `.cache/ws_customer_default/.cache/index/work_intake.v1.json`
- Decision Inbox: `.cache/ws_customer_default/.cache/index/decision_inbox.v1.json`
- Doc-nav strict: `.cache/ws_customer_default/.cache/reports/doc_graph_report.strict.v1.json`

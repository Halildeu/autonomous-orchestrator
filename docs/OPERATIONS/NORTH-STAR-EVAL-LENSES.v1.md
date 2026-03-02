# North Star Eval Lenses (SSOT) — v1.2

Bu dokuman Eval icindeki lensleri SSOT olarak kilitler.
Canonical isletim sirasi:
Define -> Theme/Subtheme Lifecycle (Seed/Consult/Gate) -> Raw -> Eval(A/B/C/...) -> Gap -> Cockpit -> PDCA.

Reuse-first kurali:
- Yeni PROJECT once Theme/Subtheme yasam dongusunu calistirir (seed/consult -> proposed -> approval -> active).
- Sonra olcum zincirini calistirir (raw -> eval -> gap -> pdca).
- Sonucunda mevcut extension/packs onerilir; eksik kalanlar icin gap uretilir ve is (PROJECT/TICKET/ROADMAP) acilir.

## Isletim Sozlesmesi: Reference -> Assessment -> Gap
- Reference (normatif hedef): trend_catalog + bp_catalog + onayli Theme/Subtheme mekanizma katalogu.
- Assessment (mevcut durum olcumu): assessment_raw + assessment_eval; sistemin referansa gore neyi sagladigini olcer.
- Gap (sapma): assessment sonucundan deterministik uretilen eksik/fark kayitlari (gap_register).

Asama sirasi (zorunlu):
1) Reference havuzunu hazirla/onayla (seed/consult/gate -> ACTIVE).
2) Assessment olcum hattini calistir (raw -> eval).
3) Gap kayitlarini uret ve onceliklendir.
4) Cockpit + PDCA ile kapatma/recheck dongusune al.

Terminoloji notu (UI):
- "Reference / Assessment / Gap" surec asamalaridir.
- Lens Findings icindeki "catalog/source type" alani (trend, bp, lens) sadece bulgunun kaynak tipidir; surec asamasi degildir.

## Not: Lens kavrami (UI vs arka plan)
- Lens, arka plan "olcum paketi"dir (eval ruleset).
- UI filtreleri "Perspective/Subject/Theme/Subtheme" odaklidir; lens UI'da filtre olarak zorunlu degildir.
- Lens secimi UI'da varsa, "olcum gozlugu" anlaminda bilgi amaçli sunulur.

## Seed / Consult / Gate (North Star Theme/Subtheme)
- Subject acilisinda GPT-Seed sadece "PROPOSED" havuza yazar.
- Consult LLM'ler yeni tema yaratmaz; sadece eksik/birlestir/azalt onerisi verir.
- PROPOSED -> ACTIVE gecisi kullanici onayi ile olur (no drift).
- LLM cikti registry'ye dogrudan yazilamaz.

## Eval-A: Trend / Best Practice
- Kaynak: bp_catalog + trend_catalog + coverage.
- Cikti: status + score + coverage.
- Kural: Trend onerisi asla direkt apply olmaz (plan-only / advisory).

## Eval-B: Integrity & Compatibility
- Kaynak: integrity_verify sonucu + uyumluluk sinyali.
- Cikti: status + score + integrity_status.
- FAIL ise Gap tarafinda kritik sinyal olarak islenir.

## Eval-C: AI-Ops Fit
- Kaynak: context_pack varligi, provider policy pin, secrets redaction.
- Cikti: status + score + requirements (booleans).
- AI-Ops Fit = yonetilebilirlik / risk / maliyet uygunlugu.

## Eval-D: GitHub Ops / Release Automation
- Kaynak: github_ops job pipeline + release manifest + network policy default OFF.
- Cikti: status + score + coverage + requirements (booleans).
- Kural: job+poll disinda bekleme yok; publish/push policy gated.

## Eval-E: Operability (Simplicity / Sustainability / Continuity)
- Kaynak: script_budget, doc_nav placeholders, airunner jobs/heartbeat, pdca cursor, work-intake noise, integrity.
- Cikti: status + score + coverage + subscores (simplicity/sustainability/continuity) + reasons[].
- Kural: Operability WARN/FAIL gap uretilir; PDCA cooldown + regression izler.

## Eval-F: Integration Coherence (Layer/Pack/Core Unlock/Schema)
- Kaynak: layer_boundary report, pack_validation report, core_unlock compliance, validate_schemas ozeti.
- Cikti: status + score + classification + reasons[] (subscores optional).
- Kural: Bu lens varsayilan olarak gate degildir; sadece olcer/uyarir/gap uretir.
- FAIL reason -> INCIDENT, WARN reason -> TICKET/PROJECT (policy gap_rules).
- PDCA, bu lens icin regression ve cooldown uygular.

## Guardrail Signals (destek)
- Guardrail sinyalleri (guardrail_signals.v1.json) lens kaynaklarina eklenir.
- Sinyal yoksa "unknown" kabul edilir; fail-closed davranis Gap uretir.

## Gap Baglantisi
- Lens status OK degilse Gap kaydi uretilir (deterministic).
- Severity haritalama: FAIL -> high, WARN -> medium.

## Cockpit / PDCA
- Lens ozeti system-status benchmark bolumune eklenir.
- PDCA, lens sinyallerini recheck/regression icin kullanir.

# North Star Eval Lenses (SSOT) — v1

Bu dokuman M10.2b Eval icindeki lensleri SSOT olarak kilitler.
Zincir: Define -> Raw -> Eval(A/B/C) -> Gap -> Cockpit -> PDCA.

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

## Gap Baglantisi
- Lens status OK degilse Gap kaydi uretilir (deterministic).
- Severity haritalama: FAIL -> high, WARN -> medium.

## Cockpit / PDCA
- Lens ozeti system-status benchmark bolumune eklenir.
- PDCA, lens sinyallerini recheck/regression icin kullanir.

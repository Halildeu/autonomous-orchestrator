# DECISION-POLICY (Karar Disiplini)

## Amac
Kararlari dosya aratarak degil, **Decision Inbox** uzerinden toplayip yonetmek.
Doer (Airrunner/exec) karar vermez; sadece "karar lazim" isaretler.

## Otomatik uygulanabilen "safe defaults"
Asagidaki kararlar otomatik bulk apply ile **guvenli varsayilan** olarak uygulanabilir:
- NETWORK_ENABLE / NETWORK_LIVE_ENABLE: **Varsayilan OFF (KEEP_OFF)**
- AUTO_APPLY_ALLOW: riskli kapsamlar icin **Varsayilan BLOCKED**
- ROUTE_OVERRIDE: yalniz "doc-only duzeltme" gibi dusuk riskli yonlendirmeler (policy izin verirse)

## Mutlaka kullanici onayi isteyen kararlar
- Network live acma (OFF disinda bir secenek)
- Core allowlist genisletme (src/ops, src/* genis kapsam)
- Deploy live (prod) tetikleme
- Merge / publish gibi geri donussuz aksiyonlar (policy ile)

## Durum siniflari
- OK: Gate'ler gecti, yapilacak kritik yok
- WARN: borc/uyari var ama calismaya devam edebilir
- FAIL: deterministik kural ihlali (orn. schema fail, hard budget, secrets leak)
- IDLE: yapilacak eylem yok veya plan/karar bekliyor (STOP degildir)
- NOOP: bilerek yan etkisiz raporlama/kanit uretimi

## Kritik hata davranisi
- Schema fail / hard budget / secrets leak => FAIL + dur
- Network kapaliyken live is => IDLE/SKIP (deterministik)
- Karar gereken is => "DECISION_NEEDED" + tick devam eder

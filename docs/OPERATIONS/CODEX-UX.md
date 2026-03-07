# CODEX-UX (Customer-friendly mode) — v0.1

Bu doküman, “kullanıcı komut yazmaz” yaklaşımını SSOT olarak tanımlar.

## Temel sözleşme

- Kullanıcı shell komutu yazmaz.
- Agent (Codex) işlemleri repo içindeki ops komutlarıyla yürütür ve sonucu standart formatta raporlar.
- Varsayılan workspace root: `.cache/ws_customer_default`
  - Yoksa agent önce `workspace-bootstrap` çalıştırır.
- Fail-closed:
  - Network default kapalıdır.
  - Side-effect’ler dry-run ve policy/gate/governor kontrolleri ile kontrol edilir.
  - Şüphede dur: `report_only` / “plan only” yaklaşımı.
- Codex runtime overlay:
  - Effective model/config repo template'ten degil, `policy_codex_runtime.v1.json` + CODEX_HOME bootstrap'tan gelir.
- Session memory:
  - Varsayilan strateji `hybrid`'dir: local session evidence korunur, provider-state/compaction referanslari ayrica tutulur.
- App automations:
  - Codex app automation tetigi repo icinde dogrudan serbest isletim yapmaz; operator/frontend olarak calisir, repo execution tarafinda `PRJ-AIRUNNER` ve ops komutlari kullanilir.
- Roadmap “living”dir:
  - SSOT roadmap dosyası güncellenirse (hash drift), agent bir sonraki bounded “Devam et” akışında stale milestone’ları otomatik yeniden çalıştırır ve bunu çıktıda `drift_detected` olarak raporlar.
- “Tek mantık” sözleşmesi (plan):
  - CAPABILITY/KABİLİYET tanımları spec-core meta (hybrid) ile standardize edilir; ISO içerikleri kopyalanmaz, `iso_refs` ile tenant ISO çekirdek dosyalarına referans verilir.
  - SSOT güncellemeleri **Change Proposals (CHG)** ile ilerler (sessiz edit yok; fail-closed).

## Kullanıcı mesajları → agent aksiyonları (örnekler)

### “Devam et”
Agent:
- Workspace durumunu okur (`roadmap-status`).
- Varsayılan: bounded şekilde `roadmap-finish` çalıştırır (ör. 3–5 dakika).
- Çıktıyı AUTOPILOT CHAT formatında döner.

### “Bir adım ilerlet”
Agent:
- Workspace durumunu okur (`roadmap-status`).
- Tek milestone ilerletir: `roadmap-follow` (max-steps=1).
- Çıktıyı AUTOPILOT CHAT formatında döner.

### “Bitir / tamamla”
Agent:
- `roadmap-finish` çalıştırır (bounded, fail-closed).
- Eğer BLOCKED ise sebebini + Action Register’ı raporlar.

### “Duraklat”
Agent:
- Workspace için `roadmap-pause` uygular.
- Sonraki çağrılarda otomatik ilerleme yapmaz; “resume” bekler.

### “Devam ettir”
Agent:
- `roadmap-resume` uygular.
- Sonra `roadmap-status` ile next milestone’ı raporlar.

### “Durumu göster”
Agent:
- Program tek kapıdan doc-nav-check (summary) ile cockpit + doc navigation özetini verir.

### “Neredeyiz?”
Agent:
- Program doc-nav-check (summary) çalıştırır.

### “Detaylı göster”
Agent:
- Program doc-nav-check (detail) çalıştırır.

### “Strict kontrol”
Agent:
- Program doc-nav-check (strict + detail) çalıştırır (core için).

## AUTOPILOT CHAT formatı (always-on)

Agent her yanıtında aşağıdaki başlıkları **sırasıyla** üretir:

SSOT: `formats/format-autopilot-chat.v1.json` (`FORMAT-AUTOPILOT-CHAT` / `v1`).

1) `PREVIEW:` (ne yapılacak / next milestone)
2) `RESULT:` (şu anki durum, OK/DONE/BLOCKED)
3) `EVIDENCE:` (kanıt yolları)
4) `ACTIONS:` (Action Register özet/öncelikler)
5) `NEXT:` (kullanıcının doğal dille yapabileceği seçenekler)

Not:
- Kullanıcıya shell komutu “kopyala‑yapıştır” olarak verilmez.
- Agent, komutları kendi içinde çalıştırır.

## Pause/Resume davranışı

- Pause aktifken otomatik ilerleme durur.
- Resume sonrası tekrar roadmap akışı devam eder.
- Pause bilgisi workspace state dosyasında tutulur:
  `<workspace-root>/.cache/roadmap_state.v1.json`

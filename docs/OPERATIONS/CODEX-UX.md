# CODEX-UX (Customer-friendly mode) — v0.1

Bu doküman, “kullanıcı komut yazmaz” yaklaşımını SSOT olarak tanımlar.

## Temel sözleşme

- Kullanıcı shell komutu yazmaz.
- Agent (Codex) işlemleri repo içindeki ops komutlarıyla yürütür ve sonucu standart formatta raporlar.
- Varsayılan workspace root: `.cache/ws_customer_default`
  - Yoksa agent önce `workspace-bootstrap` çalıştırır.
  - User-facing ops çağrılarında repo root `.` verilirse program canonical customer workspace'e normalize eder.
- Fail-closed:
  - Network default kapalıdır.
  - Side-effect’ler dry-run ve policy/gate/governor kontrolleri ile kontrol edilir.
  - Şüphede dur: `report_only` / “plan only” yaklaşımı.
- Codex runtime overlay:
  - Effective model/config repo template'ten degil, `policy_codex_runtime.v1.json` + orchestrator bootstrap'tan gelir (CODEX_HOME yalniz runner ic kullaniminda set edilir; interactive CLI'da export etmeyin).
- Session memory:
  - Varsayilan strateji `hybrid`'dir: local session evidence korunur, provider-state/compaction referanslari ayrica tutulur.
  - OpenAI `Responses` devam zinciri kullaniliyorsa son `response_id` session context'e yazilir ve sonraki canli cagrida `previous_response_id` olarak tekrar kullanilir.
  - Girdi token tahmini runtime limitini asarsa workspace altinda compaction özeti uretilir; bu artefact session context ve cross-session raporunda gorunur.
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

### “Board durumunu göster”
Agent:
- Bunu `Governance Board Capability v1` ürün akışı olarak ele alır.
- Canlı GitHub ProjectV2 durumunu report-only okur.
- Varsayılan güvenli sıra: `board-projection-live`, `board-metadata-live`,
  sonra `board-sync --mode dry-run`.
- Issue close, `Done`, PR mutation veya broad backlog backfill yapmaz.
- Çıktıda `Needs Verify` ile `Done` ayrımını açık raporlar.

### “Board doğrulamasını ilerlet”
Agent:
- Bunu `Governance Board Capability v1` acceptance akışı olarak ele alır.
- Önce accepted projection digest ve target board id uyumunu doğrular.
- Apply gerekiyorsa explicit confirmation + token env + mutation ledger
  zorunludur.
- Uygulama kapsamını tek issue/item veya açıkça kabul edilmiş projection ile
  sınırlar.
- `Done`/issue close için ayrıca gerçek kabul kanıtı ve ayrı gate gerekir.

### “Board governance managed repolara dağıt”
Agent:
- Bunu `Governance Board Capability v1` managed repo rollout akışı olarak ele alır.
- Canonical kaynak:
  `docs/OPERATIONS/BOARD-GOVERNANCE-MANAGED-REPO-ROLLOUT.v1.md`.
- Önce `standards.lock` ve `.cache/managed_repos.v1.json` hedeflerini doğrular.
- Varsayılan güvenli sıra: local standards validation, managed repo dry-run,
  sonra yalnız registered manifest hedefleri için apply + validation.
- Unregistered repo, broad GitHub mutation, issue close veya `Done` işlemi
  yapmaz.

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

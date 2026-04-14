# Multi-Agent Worktree Workflow — Runbook v1

**Kim için:** Bu repoyu paralel birden fazla Claude/Codex oturumuyla kullanan kişi.
**Amaç:** Aynı anda birden fazla dev çalışması yürüten bir operatörün, iş kaybı yaşamadan, görünürlükle ve standart komutlarla ilerlemesi.

## Otorite ve İlişkiler

Bu doküman **rehber** katmanıdır. Canonical otorite:

- `standards.lock`
- `docs/OPERATIONS/AI-MULTIREPO-OPERATING-CONTRACT.v1.md`
- `docs/OPERATIONS/OPO-AUTHORITY-MAP.v1.md`
- `policies/policy_multi_agent_coordination.v1.json` (SSOT — worktree kuralları)

Çelişki olursa canonical otorite kazanır. Bu runbook pratik kullanımı anlatır, kural üretmez.

## Tek Giriş Noktası: `scripts/ops/wt`

Multi-agent worktree operasyonları için tek entry point. Hook'lara, registry'ye ve safety ref'lere köprü.

```
wt init            # idempotent bootstrap (hooks + reflog + exclude)
wt new <name>      # yeni worktree açar (origin/main'den, upstream temiz)
wt list            # tüm worktree'leri listeler
wt status [--json] # detaylı durum: dirty, unpushed, ahead/behind, risk hint
wt sync            # origin/main'e rebase + push (safety ref önce bırakılır)
wt close           # worktree kapatır (dirty/unpushed BLOCK eder)
wt gc              # eski safety ref'leri temizler
wt help
```

Ayrıntılı parametreler için `wt <cmd> --help`.

## 4 Temel Kural (AGENTS.md §0d hatırlatma)

1. **1 agent = 1 worktree** — her sohbet kendi worktree'sinde çalışır.
2. **Her branch main'den** — zincirleme YASAK; dependency varsa explicit stacked PR.
3. **Canonical tree'de commit/push YASAK** — override sadece `ALLOW_CANONICAL_COMMIT=1 CANONICAL_OVERRIDE_REASON="..."` ile.
4. **Worktree hook'ları light mode** — full gate yalnız CI'da.

## Günlük Akış (happy path)

```bash
# 1. Yeni iş başlat
cd /Users/halilkocoglu/Documents/dev       # canonical (veya herhangi bir yer)
scripts/ops/wt new add-logout-btn          # claude/add-logout-btn branch'i
cd .claude/worktrees/add-logout-btn        # worktree'ye geç

# 2. Çalış — normal commit döngüsü
git add <files>
git commit -m "feat: ..."

# 3. Durumu gör (istediğin her an)
../../../../../scripts/ops/wt status        # veya daha önce `wt` ini PATH'e ekledin ise `wt status`

# 4. Main ilerlediyse senkronize et
../../../../../scripts/ops/wt sync         # safety ref + rebase + push

# 5. İş bitince
../../../../../scripts/ops/wt close        # dirty/unpushed yoksa kapanır
```

> İpucu: `alias wt="$(git rev-parse --git-common-dir)/../scripts/ops/wt"` — kabuk profiline ekle, her yerden `wt` kullan.

## 6 Yüksek Frekanslı Senaryo

### Senaryo 1 — "Main ilerledi, branch'im geride"

**Belirti:** `wt status` satırında `BEHIND` > 0, muhtemelen `stale>N` risk hint'i.

**Çözüm:**
```bash
wt sync
```

İç işleyiş:
1. `fetch --prune`
2. Dirty ise abort (`--autostash` opt-in)
3. Safety ref: `refs/wt-snap/<branch>/pre-sync-<ts>`
4. `rebase origin/main`
5. Upstream yoksa `push -u origin <branch>`, varsa `push --force-with-lease`

### Senaryo 2 — "Rebase conflict oldu"

**Belirti:** `wt sync` çıktısında REBASE CONFLICT mesajı, rebase yarıda.

**Çözüm (manuel):**
```bash
# Conflict'li dosyaları düzelt (editörde <<<<<<< markerlarını çöz)
git add <resolved-files>
git rebase --continue

# Ya da iptal et ve safety ref'e dön:
git rebase --abort
git reset --hard refs/wt-snap/<branch>/pre-sync-<ts>
```

Safety ref her zaman geri dönüş noktası. `wt gc` 30 günden eski olanları temizleyene kadar kalır.

### Senaryo 3 — "Yanlış tree'ye commit yaptım"

**Belirti:** Canonical tree'de commit ettin, side worktree'n dururken. Multi-agent-guard normalde bunu engeller ama override kullandıysan veya hook kapalıydıysa olabilir.

**Çözüm:**
```bash
cd /Users/halilkocoglu/Documents/dev       # canonical
git log -1                                  # hangi commit'i düşüreceğini gör
git reset --soft HEAD~1                     # commit'i dağıt, değişiklikleri staged tut
git stash                                   # staged + unstaged'i stash'e al
cd .claude/worktrees/<doğru-worktree>       # doğru yere geç
git stash pop                               # orada uygula, commit et
```

Veya commit doğru dursun, cherry-pick ile kopyala:
```bash
cd .claude/worktrees/<doğru-worktree>
git cherry-pick <sha>
cd -  # canonical
git reset --hard HEAD~1                     # canonical'da geri al (DİKKAT: başka uncommitted iş yoksa)
```

### Senaryo 4 — "Branch switch yaparken uncommitted iş kaybım olur mu?"

**Belirti:** Başka branch'e geçmen gerek ama dirty dosyalar var.

**Çözüm (yerleşik refleks):**
```bash
git stash push -m "wip: <kısa-not> $(date -u +%Y-%m-%dT%H-%M-%S)"
# artık branch değiştirebilirsin
git checkout <other-branch>
# geri döndüğünde:
git checkout <original-branch>
git stash pop
```

Worktree kullanıyorsan: **branch switch etmek ZORUNDA değilsin**. Her iş kendi worktree'sinde. Sadece `cd` ile dolaşırsın.

### Senaryo 5 — "Başka oturum aynı dosyada çalışıyor"

**Belirti:** `wt status` gösteriyor ki canonical + başka side worktree aynı dosyayı dirty tutuyor. Merge zamanı çakışma kesin.

**Çözüm:**
1. İki tarafı da **ayrı branch'e commit et** (stash ile risk alma)
2. Bir taraf **önce merge** olsun
3. Diğer taraf `wt sync` ile yeni main'den rebase etsin → conflict varsa çözsün

Conflict çözümü sırasında safety ref otomatik bırakılır (`refs/wt-snap/<branch>/pre-sync-<ts>`). İşler karışırsa:
```bash
git rebase --abort
git reset --hard refs/wt-snap/<branch>/pre-sync-<ts>
```

### Senaryo 6 — "Silinen branch'i / commit'i geri getir"

**Belirti:** Yanlışlıkla `git branch -D` yaptın, ya da `reset --hard` bir şeyleri kaybettirdi.

**Çözüm — 3 aday kaynak:**

```bash
# a) Safety refs (en yüksek başarı oranı)
git for-each-ref refs/wt-snap/ --format='%(refname) %(objectname:short) %(subject)' \
  | grep <branch-adı>
git update-ref refs/heads/<branch-adı> <sha>    # branch'i yeniden yarat

# b) Reflog (son 180 gün, wt init ayarladı)
git reflog --all | grep <branch-adı | commit-mesajından-bir-kelime>
git update-ref refs/heads/<branch-adı> <sha>

# c) Remote (eğer push edilmişse)
git fetch origin <branch-adı>
git checkout -b <branch-adı> origin/<branch-adı>
```

## Risk Hint'leri (`wt status` çıktısı)

| Hint | Anlamı | Ne yapmalı |
|---|---|---|
| `no-upstream+unpushed` | Local-only commit var; fiziksel kayıp riski | `wt sync` veya `git push -u origin <branch>` |
| `upstream=origin/main(!)` | Push main'e gider (BOMBA) | `git branch --unset-upstream`; ilk `wt sync` düzeltir |
| `stale>N` | N commit `origin/main`'den geride | `wt sync` (küçükken konflikt de küçük olur) |
| `unregistered` | Worktree registry'de yok (ghost session) | `wt init` veya `python3 scripts/check_worktree_hygiene.py` + manuel adopt |

## Safety Ref Namespace

| Ref pattern | Ne zaman oluşur |
|---|---|
| `refs/wt-snap/<branch>/pre-sync-<ts>` | `wt sync` rebase öncesi |
| `refs/wt-snap/<branch>/autostash-<ts>` | `wt sync --autostash` stash öncesi |
| `refs/wt-snap/<branch>/pre-close-<ts>` | `wt close` öncesi |
| `refs/wt-snap/canonical/head-<ts>` | Manuel `git update-ref` (acil yedek) |
| `refs/wt-snap/canonical/uncommitted-<ts>` | Manuel `git stash create` + update-ref |

Temizlik: `wt gc` (30 günden eski, branch başına son 3'ü korur).

## Anti-Pattern'lar

- **`git push` (upstream set etmeden)** — `wt sync` ilk push'u `-u` ile yapar; manuel push'ta `-u origin <branch>` unutulursa upstream yanlış kalır
- **`git pull`** — rebase yerine merge yapar, history kirli; yerine `wt sync`
- **`git reset --hard` blanket** — safety ref'e bakmadan kullanma; Bash deny listesinde zaten
- **Canonical tree'de geliştirme** — hook block eder; override gerçek acil (hotfix) için
- **Branch zincirleme (`feat/B` from `feat/A`)** — policy yasak; explicit stacked PR kullan
- **Manuel registry edit** — `.worktree-registry.json`'ı elle düzenleme; `wt` komutları yazar

## Sıkça Sorulanlar

**Q: `wt` PATH'te değil, her seferinde tam yol yazmak zor.**
A: Kabuk profiline ekle:
```bash
alias wt="$(git rev-parse --git-common-dir)/../scripts/ops/wt"
```
Veya `~/bin/wt` symlink:
```bash
ln -s /Users/halilkocoglu/Documents/dev/scripts/ops/wt ~/bin/wt
```

**Q: `wt init` güvenli mi, her zaman çalıştırılabilir mi?**
A: Evet, idempotent. Eksik şeyleri yapar, var olanları değiştirmez. `--dry-run` ile önce görebilirsin.

**Q: Bir branch'i hem canonical hem side worktree'de checkout edebilir miyim?**
A: Git izin vermez (aynı branch iki worktree'de olamaz). `wt new` her worktree için yeni branch üretir.

**Q: Safety ref'ler git geçmişimi şişirir mi?**
A: Hayır, ayrı namespace (`refs/wt-snap/`), `git log` ve `git branch` çıktılarında görünmez. `for-each-ref refs/wt-snap/` ile listelenir, `wt gc` ile temizlenir.

**Q: PR merge'inden sonra side worktree ne yapar?**
A: `wt close` ile kapat (branch silinir, remote silinir `--delete-branch` ile PR merge'inde). Sonra `wt new <yeni-iş>`.

## İlgili Yapı

- Policy: `policies/policy_multi_agent_coordination.v1.json`
- Registry: `<canonical-root>/.worktree-registry.json` (gitignored, runtime)
- Hygiene check: `scripts/check_worktree_hygiene.py`
- Multi-agent guard: `scripts/multi-agent-guard.sh`
- Hook installer: `scripts/setup_local_git_hooks.sh`
- Open/close session scripts: `scripts/ops/open_worktree_session.py`, `scripts/ops/close_worktree_session.py`

## Revision Log

| Tarih | Revizyon | Değişiklik |
|---|---|---|
| 2026-04-14 | v1.0 | İlk revizyon — `wt` wrapper + 6 senaryo + safety ref namespace dokümante |

# Release Strategy (Milestones as SSOT)

Amaç: Her küçük değişiklik için GitHub Release yayınlayıp zaman kaybetmemek; buna rağmen ana branşın hızlı, güvenli ve denetlenebilir kalmasını sağlamak.

## Principles

- **Main hızlı akar:** PR merge etmek için şartımız CI gate’lerinin yeşil olmasıdır.
- **GitHub Release yalnızca milestone sürümlerde:** örn. `v0.2.0`, `v0.3.0`, `v1.0.0`.
- **Checkpoint tag’leri serbest (opsiyonel):** iç koordinasyon için lightweight tag atılabilir; GitHub Release çıkmak zorunlu değildir.
- **SSOT dokümanlar:** `CHANGELOG.md` + `docs/OPERATIONS/release-notes-v1.0.0.md` + bu doküman.

## What qualifies as a milestone release

Aşağıdakilerden en az biri varsa milestone release düşün:

- Yeni **kullanıcı-facing intent/workflow** (örn. yeni `urn:*` intent).
- Güvenlik/yan etki davranışında anlamlı değişiklik (policy, tool gateway, side-effect enforcement).
- Paketleme/CLI UX değişikliği (yeni CLI komutu, davranış değişimi, breaking/semantics change).

## What does NOT require a GitHub Release

Genellikle milestone release gerektirmeyen değişiklikler:

- Refactor (davranış değişikliği yoksa).
- Dokümantasyon güncellemeleri.
- Smoke test genişletmeleri / internal tooling.
- Küçük ve “safe” bugfix’ler (user-facing davranışı değiştirmiyorsa).

Bu tür değişiklikler için hedef:
- `main` yeşil kalsın
- “weekly checkpoint review” yapılsın
- milestone birikince release yapılsın

## Cadence

- **Weekly checkpoint (öneri):**
  - `policy-check` raporu üret, gözden geçir, gerekiyorsa aksiyon al.
- **Milestone window (hazır olduğunda):**
  - Milestone kriterlerinden biri yakalandığında planlı release yap.

## Procedure (copy‑paste)

Repo root’ta:

```bash
# 1) End-to-end sanity
python smoke_test.py

# 2) Policy impact review (fixtures + evidence history)
python -m src.ops.manage policy-check --source both

# 3) Supply-chain sanity (local dev uses DEV_KEY fallback; CI requires secret)
python supply_chain/sbom.py
python supply_chain/sign.py
python supply_chain/verify.py
python supply_chain/license_gate.py
python supply_chain/cve_gate.py
```

Milestone release yayınlama (manual kısmı):

1) Tag:

```bash
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

2) GitHub Release (UI):
- `CHANGELOG.md` içindeki ilgili sürüm bölümünü (veya `docs/OPERATIONS/release-notes-v1.0.0.md`) description olarak yapıştır.

## Optional: internal checkpoint tags (no GitHub Release)

Küçük checkpoint için örnek:

```bash
git tag -a checkpoint-YYYYMMDD -m "checkpoint YYYYMMDD"
git push origin checkpoint-YYYYMMDD
```

Not: Bu tag’ler opsiyoneldir; PR review + CI yeşil olduğu sürece sistemin “main flows fast” hedefini bozmaz.

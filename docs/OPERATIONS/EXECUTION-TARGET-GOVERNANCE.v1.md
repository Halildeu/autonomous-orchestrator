# EXECUTION-TARGET-GOVERNANCE.v1

## 1. Amac

Bu dokuman, bir AI veya otomasyon bir run baslatmadan once
`hangi repo / hangi target / hangi launch / hangi branch / hangi worktree`
uzerinde calisabilecegini belirleyen governance modelini tanimlar.

Ana ilkeler:

- target discovery tahminle degil registry ile yapilir
- authority search ile degil authority matrix ile belirlenir
- archived/backup/legacy alanlar canli target sayilmaz
- product catalog modul truth tasir, launch truth tasimaz

## 2. In-Scope

- aktif repo kaydi
- aktif target kaydi
- launch profile kaydi
- version source kaydi
- authority ve duplicate kontrolu
- worktree/workspace saglik sinyallerinin resolve sirasina baglanmasi

## 3. Out-of-Scope

- provider/model secimi
- role/actor atamasi
- handoff/closeout envelope
- second-writer lock implementation
- `src/**` runtime wiring

## 4. Zorunlu Girdiler

Run baslamadan once su canonical veya derived kaynaklar okunur:

1. `registry/active_execution_registry.v1.json`
2. `registry/apps_and_launch_registry.v1.json`
3. `registry/version_registry.v1.json`
4. `registry/authority_matrix.v1.json`
5. `registry/duplicate_surface_register.v1.json`
6. `policies/policy_execution_target_governance.v1.json`
7. varsa `.cache/reports/worktree_health.v1.json`
8. apply sinifi islerde gerekiyorsa `ai_entry_pack`

## 5. Resolve Sirasi

1. kullanici niyeti veya work item target ipucu okunur
2. target yalniz `active_execution_registry` icinde resolve edilir
3. launch yalniz `apps_and_launch_registry` icinde resolve edilir
4. version source `version_registry` icinde kontrol edilir
5. authority ve duplicate etkisi okunur
6. execution target policy ve worktree health sinyalleri uygulanir
7. ancak bundan sonra plan/apply baslar

## 6. Block Kurallari

Asagidaki durumlarda run fail-closed durur:

- unknown target
- unknown repo root
- archived target
- backup target
- legacy target
- unapproved worktree
- unknown version source
- launch profile kaydi yok

Asagidaki durumlar baslangicta `report_only` veya `warn` olabilir:

- dirty tree
- no upstream
- stale checkout
- wrong branch
- detached head

## 7. Evidence Kurallari

Her resolve kaydinda su alanlar zorunludur:

- `repo_id`
- `target_id`
- `repo_root`
- `working_dir`
- `branch`
- `head`
- `launch_profile_id`
- `version_source_refs`
- `selection_reason`

## 8. Runtime Sinirlari

- filesystem discovery fallback yok
- `docs/OPERATIONS/product_catalog.v1.json` launch registry yerine gecmez
- `.cache/managed_repos.v1.json` umbrella repo truth tasir; app/worktree/launch truth tasimaz
- workspace-derived artefact canonical authority yerine gecmez

## 9. Promotion Kurali

Bu governance modeli once non-src olarak promote edilir:

- `registry/*.v1.json`
- `schemas/*.schema.json`
- `policies/policy_execution_target_governance.v1.json`
- `docs/OPERATIONS/EXECUTION-TARGET-GOVERNANCE.v1.md`

Runtime wiring ve governor integration daha sonra dar kapsamli
`ONE_SHOT_SRC_WINDOW` ile yapilir.

## 10. Done

Bu model aktif kabul edilmek icin:

- target resolve registry-first calisir
- launch resolve registry-first calisir
- wrong target ve archived target fail-closed durur
- authority/duplicate etkisi resolution sirasinda okunur
- apply sinifi isler target evidence olmadan baslamaz

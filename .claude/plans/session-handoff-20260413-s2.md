# Session Handoff — 2026-04-13 Session 2

## Bu Session Ne Yapti (23 is)

### PR #356 (claude/loving-golick → main, host'ta merge edildi)

**Zanzibar Gap Analizi:**
- Codex istisaresi CNS-20260413-002 (440K token, gpt-5.3-codex)
- 20 boslugun severity matrix + aksiyon plani

**Kod Degisiklikleri:**
1. MF React singleton fix — isSingleDomainBuild kaldirildi, shared config birlesti (5 vite.config.ts)
2. Schema-service CORS wildcard+credentials → allowlist
3. OpenFGA healthcheck NONE → gercek probe
4. Prod'da OpenFGA Playground kapatildi
5. AuthzGuardFilter — authz endpoint rate limiter (60 req/min)
6. OpenFgaCircuitBreaker — pure Java CB (5 fail → 30s open)
7. Grafana alert rules — outbox dead letter + CB state
8. Deprecated PERMISSIONS constants kaldirildi (shell)
9. doctor-zanzibar.sh — Section C compose kontrolleri (C1-C7)

**Sunucu Altyapi Fix'leri:**
10. Permission-service Eureka kaydi (EUREKA_CLIENT_SERVICE_URL_DEFAULTZONE eksikti)
11. OpenFGA Store/Model ID .env'e yazildi
12. SecurityConfigLocal → configurable SECURITY_LOCAL_DEV_USER_ID=1201
13. authz/me dev fallback (JWT null → superAdmin response)
14. THEME module DB'ye eklendi (permission_id=105)
15. Report-service profil fix (prod → local,docker) + Eureka IP + PG password
16. Compose name: serban → platform
17. CI runner containerlari temizlendi (tek compose'dan)
18. Keycloak nginx proxy → 127.0.0.1:8081 (kalici, host port)
19. Deploy script default NGINX_KEYCLOAK_UPSTREAM → 127.0.0.1:8081
20. service-manager read-only mount fix (./scripts:/app writable)
21. */5 cron deploy devre disi birakildi
22. Host repo temizlendi + PR branch merge edildi
23. .env.example → COMPOSE_PROJECT_NAME=platform eklendi

## BLOCKER — Ilk Cozulecek Is

### MF React Duplicate Instance

**Sorun:** ai.acik.com beyaz ekran. Console:
```
TypeError: Cannot read properties of null (reading 'useMemo')
Shell: react-gawBNo26.js
Users remote: react-dom-ePOBNC5H.js
```

**Neden:** isSingleDomainBuild conditional kaldirildi ama @module-federation/vite 1.14 singleton negotiation production build'de calismiyor. Iki ayri react-dom chunk olusturuluyor.

**Cozum yolu:**
1. Shell'de react/react-dom'a `eager: true` ekle
2. Remote'larda `import: false` dene
3. Lokal dev server'da tarayicida test et
4. Deploy et

## Kararlar (Bu Session)

| # | Karar | Sonuc |
|---|-------|-------|
| K-7 | Staging canonical runtime | Dev compose (docker-compose.yml) |
| K-8 | Nginx yonetimi | Standalone script (compose disi) |
| K-9 | Cron deploy | Disabled (stabilizasyon tamamlanana kadar) |
| K-10 | Keycloak proxy | 127.0.0.1:8081 (host port, kalici) |

## Sunucu Bilgileri

- SSH: ssh staging-sw (10.9.10.53)
- Web root: /home/halil/platform/web/current → releases/bcf0c5ab-mf-fix
- Backend: /home/halil/platform/repo/backend/docker-compose.yml (name: platform)
- .env: /home/halil/platform/repo/backend/.env
- Vault token: (backend .env dosyasinda — VAULT_TOKEN)
- Vault unseal: (.vault-dev/unseal-key dosyasinda)
- OpenFGA store: 01KNF4FYY8NQJR655D0WXK6607
- OpenFGA model: 01KNX1PH3V4EQE4K25H8D77PHX
- Keycloak: admin1@example.com / admin1234 (DB id=1203)
- Dev admin: SECURITY_LOCAL_DEV_USER_ID=1201
- Cron: DISABLED (yedek: /home/halil/platform/state/crontab.backup.*)

## Kalan Isler

### P0 — BLOCKER
1. MF React singleton fix (eager/import false dene, lokal test, deploy)

### P1 — Bu Sprint
2. Deploy script fail-closed yap
3. Cron deploy'u guvenli yeniden ac

### P2 — Sonraki Sprint
4. A3: Security headers hardening
5. C2: Tuple reconciliation batch job
6. B2: OpenFGA model migration/versioning
7. E1/E2: Grafana paneller genisletme

### P3 — Backlog
8. react-router-dom v7 migration (3-5 gun)
9. zod v4 migration
10. Explain drawer/modal (Faz 4)
11. Test kapsam genisletme

## Worktree

- Aktif: loving-golick
- Branch: claude/loving-golick
- Base: main @ 3d12c136

## Sonraki Session Baslangic

```
1. Plan oku: .claude/plans/zanzibar-master-plan.md
2. Handoff oku: .claude/plans/session-handoff-20260413-s2.md
3. BLOCKER: MF React singleton — lokal test + deploy
4. Deploy script fail-closed
5. Cron yeniden ac
```

## Codex Istisare

- ID: CNS-20260413-002
- Token: 440,748
- Kabul: A2 duzeltme, MF surum drift, Resilience4j, batch reconciliation

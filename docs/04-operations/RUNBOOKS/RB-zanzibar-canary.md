# RB-zanzibar-canary – Zanzibar Canary Deployment Runbook

ID: RB-zanzibar-canary
Service: permission-service, core-data-service, openfga
Status: Draft
Owner: @halil

-------------------------------------------------------------------------------
1. AMAÇ
-------------------------------------------------------------------------------

Zanzibar authorization sisteminin staging'den production'a feature-flag ile
kademeli gecisini yonetmek. Ref: CNS-20260411-001, Dalga 2 Plan.

-------------------------------------------------------------------------------
2. KAPSAM
-------------------------------------------------------------------------------

- Sorumlu: Platform Engineering (operasyon), @halil (owner).
- Ortamlar: stage (canary), prod (rollout).
- Servisler: permission-service, core-data-service, user-service, variant-service, openfga.
- SLA: Authz check p95 < 50ms, error rate < 0.5%, deny rate < 10%.

Pre-conditions:
- [ ] Dalga 1+2 PR'lar merged
- [ ] Staging 24h stable (error rate < 0.1%)
- [ ] doctor-zanzibar.sh PASS (pre-existing haric)
- [ ] Restricted smoke user seeded (stage-keycloak-smoke-user seed-smoke-role)

-------------------------------------------------------------------------------
3. BAŞLATMA / DURDURMA
-------------------------------------------------------------------------------

Stage 1 — Deploy (Flags OFF, Day 1):
1. Merge main branch to prod deploy.
2. docker compose pull && docker compose up -d
3. Verify: all containers healthy.
4. Verify: ERP_OPENFGA_ENABLED=false in all services.
5. Run: smoke-zanzibar.yml workflow (manual dispatch).
Rollback: Standard rollback (previous image tag).

Stage 2 — Canary (Flags ON, Admin + Restricted, Day 2-4):
1. Set ERP_OPENFGA_ENABLED=true for permission-service + core-data-service.
2. Set SCOPE_CACHE_ENABLED=true, AUTHZ_VERSION_ENABLED=true.
3. Restart: docker compose restart permission-service core-data-service
4. Monitor 48h (guardrails below).
5. Run restricted probe: zanzibar-restricted-probe.sh
   - superAdmin=false, THEME denied, ACCESS granted.
Rollback: ERP_OPENFGA_ENABLED=false + restart (< 1 min).

Stage 3 — Full Rollout (Day 5-14):
- Stage 2 stable 48h → keep flags ON.
- No traffic splitting (not applicable for current architecture).

-------------------------------------------------------------------------------
4. GÖZLEMLEME / LOG / METRİKLER
-------------------------------------------------------------------------------

Guardrails:

| Metric                 | Threshold | Action on Breach                    |
|------------------------|-----------|-------------------------------------|
| authz_check_p95_ms     | > 50ms    | Investigate cache, consider warm-up |
| authz_check_p95_ms     | > 150ms   | Rollback (flags OFF)                |
| authz_deny_rate_pct    | > 10%     | Investigate model, check tuple sync |
| authz_error_rate_pct   | > 0.5%    | Rollback (flags OFF)                |
| authz_cache_miss_rate  | > 50%     | Check TTL, cache size               |
| OpenFGA down           | up == 0   | Fail-closed active, rollback flags  |

Loglar:
- docker logs serban-permission-service-1 --tail 200
- docker logs serban-openfga-1 --tail 200

Metrikler:
- Prometheus: http://localhost:9090 (permission-service, core-data, openfga targets)
- Grafana: authz-zanzibar alert rules (6 rule)

-------------------------------------------------------------------------------
5. ARIZA DURUMLARI VE ADIMLAR
-------------------------------------------------------------------------------

- [ ] Ariza senaryosu 1 — OpenFGA down:
  - Given: OpenFGA container crashed veya network partition.
    When: up{job="openfga"} == 0 alert fires.
    Then: Fail-closed aktif (tum check'ler true doner). Flags OFF + restart.

- [ ] Ariza senaryosu 2 — Yuksek deny rate:
  - Given: authz_deny_rate_pct > 10%.
    When: Model regression veya tuple sync hatasi.
    Then: doctor-zanzibar.sh calistir, tuple dump incele, rollback flags.

- [ ] Ariza senaryosu 3 — Cache miss storm:
  - Given: authz_cache_miss_rate > 50% sustained.
    When: Version bump loop veya TTL cok kisa.
    Then: SCOPE_CACHE_TTL_SECONDS artir (30 → 60), cache size kontrol.

-------------------------------------------------------------------------------
6. ÖZET
-------------------------------------------------------------------------------

- Canary 3 asamali: deploy (OFF) → canary (ON, admin+restricted) → rollout.
- Rollback her asamada < 1 dk (flag OFF + restart).
- Restricted user deny senaryosu canary'nin zorunlu parcasi.

-------------------------------------------------------------------------------
7. LİNKLER (İSTEĞE BAĞLI)
-------------------------------------------------------------------------------

- Master plan: .claude/plans/zanzibar-master-plan.md (rev 4)
- Decision registry: decisions/topics/zanzibar-openfga.v1.json
- Guardrails config: backend/scripts/ci/canary/zanzibar-guardrails.json
- Doctor script: backend/scripts/doctor-zanzibar.sh
- Restricted probe: backend/scripts/ci/canary/zanzibar-restricted-probe.sh

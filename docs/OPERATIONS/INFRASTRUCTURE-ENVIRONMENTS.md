# Infrastructure Environments

## Compose Kullanim Haritasi

| Ortam | Compose | Image | Profile | Kullanim |
|-------|---------|-------|---------|----------|
| Lokal (macOS) | backend/docker-compose.yml | Lokal build | local,docker | Gelistirici |
| Staging (Ubuntu) | backend/docker-compose.yml | Lokal build | local,docker | Test (ai.acik.com) |
| Production (Ubuntu) | deploy/docker-compose.prod.yml | GHCR registry | prod | Canli |

## Kurallar

1. backend/docker-compose.yml: lokal build, GHCR referansi OLMAMALI
2. deploy/docker-compose.prod.yml: GHCR image, lokal build OLMAMALI
3. Iki dosya ayni servisleri tanimlamali (doctor-infra.sh H)
4. Staging'de COMPOSE_FILE env var prod'a isaret ETMEMELI (doctor-infra.sh I)

## Stabilizasyon Garantileri

- Keycloak: PostgreSQL backend (KC_DB=postgres) — H3
- Keycloak: KC_HEALTH_ENABLED=true — H4
- Keycloak: Healthcheck port 9000 — H5
- OpenFGA: Playground kapali (prod) — H6
- Nginx: proxy_pass 127.0.0.1 (host network) — A1-A3
- Eureka: prefer-ip-address=true — C1
- Vault: Otomatik acma yapilandirmasi — F4
- Compose: Tek proje ismi platform — B7, H2

## CI Gate

doctor-infra.sh: 54 check, 9 section (A-I), ci-gate-infra job.

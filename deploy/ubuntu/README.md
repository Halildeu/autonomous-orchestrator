# Ubuntu Backend Deploy

Bu klasör GitHub-first backend deploy akışının Ubuntu tarafındaki scriptlerini içerir.

## Akış

1. GitHub Actions backend image'larını GHCR'ye push eder.
2. Host üzerindeki `backend.env` dosyası Vault'tan render edilmiş halde bulunur.
3. Workflow SSH ile Ubuntu host'a bağlanır.
4. `deploy-backend.sh` repo'yu GitHub'dan senkronize eder, GHCR image'larını çeker ve `docker compose up -d` çalıştırır.
5. `rollback-backend.sh` bir önceki image tag'ine geri döner.

## Host ön koşulları

- `git`
- `docker` + Compose v2
- `curl`
- `python3`
- `/home/halil/platform/env/backend.env`
- GitHub repo clone erişimi (`GIT_REMOTE_URL`)
- GHCR read erişimi deploy workflow tarafından ephemeral olarak taşınır
- Backend deploy secret'ları için önerilen GitHub target'ı environment bazlı `stage` / `prod` secret setidir
- AppRole tabanlı render kullanılacaksa:
  - `/home/halil/platform/state/vault/approle/backend-deploy-<env>.role-id`
  - `/home/halil/platform/state/vault/approle/backend-deploy-<env>.secret-id`

## Vault sözleşmesi

- Canonical deploy env path'i: `secret/<env>/backend-deploy/config`
- Canonical GitHub backend deploy secret path'i: `secret/<env>/ops/github/backend-deploy`
- Host üzerindeki materialized env dosyası:
  - `/home/halil/platform/env/backend.env`
- Render script:
  - `deploy/ubuntu/render-backend-env.sh`
- AppRole render wrapper:
  - `deploy/ubuntu/render-backend-env-approle.sh`
- Preflight script:
  - `backend/scripts/vault/check-backend-deploy-stage.sh`
  - `backend/scripts/vault/check-backend-deploy-prod.sh`
- AppRole credential materializer:
  - `backend/scripts/vault/materialize-backend-deploy-approle.sh`

Örnek kullanım:

```bash
mkdir -p "$HOME/platform/env"

export VAULT_ADDR="https://vault.example.com"
export VAULT_TOKEN="..."
export DEPLOY_ENV="stage"

deploy/ubuntu/render-backend-env.sh
```

AppRole ile render:

```bash
ENV=stage \
VAULT_ADDR="https://vault.example.com" \
VAULT_TOKEN="..." \
bash backend/scripts/vault/materialize-backend-deploy-approle.sh

export DEPLOY_ENV="stage"
export VAULT_ADDR="https://vault.example.com"

deploy/ubuntu/render-backend-env-approle.sh
```

Vault preflight:

```bash
ENV=stage \
VAULT_ADDR="https://vault.example.com" \
VAULT_TOKEN="..." \
bash backend/scripts/vault/check-backend-deploy-stage.sh
```

## GitHub Secrets

- `BACKEND_SSH_DEPLOY_ENABLED`
- `BACKEND_DEPLOY_SSH_HOST`
- `BACKEND_DEPLOY_SSH_PORT`
- `BACKEND_DEPLOY_SSH_USER`
- `BACKEND_DEPLOY_SSH_KEY`
- `BACKEND_DEPLOY_SSH_KNOWN_HOSTS`
- `BACKEND_DEPLOY_REMOTE_ENV_FILE` (opsiyonel)
- `BACKEND_DEPLOY_REMOTE_REPO_DIR` (opsiyonel)
- `BACKEND_DEPLOY_REMOTE_COMPOSE_PROFILES` (opsiyonel)
- `BACKEND_HEALTH_URLS`

Bu secret'lar elle yazılmak zorunda değil. `vault-secrets-sync.yml` artık `mode=backend-deploy` ile `secret/<env>/ops/github/backend-deploy` path'inden GitHub Actions secret'larına senkron yapabiliyor.

Önerilen hedef:
- `stage` backend secret'ları GitHub `stage` environment'ına yazılır
- `prod` backend secret'ları GitHub `prod` environment'ına yazılır
- Repo-level duplicate secret'lar merge sonrası temizlenir

## GHCR erişimi

- `stage` için self-hosted veya SSH tabanlı deploy kullanıldığında GitHub Actions runtime token'ı ephemeral geçirilebilir.
- `prod` private network arkasındaysa önerilen model `pull-based` promote'tur.
- `pull-based` modda host kendi `backend.env.prod` dosyasından `GHCR_USERNAME` ve `GHCR_TOKEN` okuyarak `main-stable` image setini çeker.
- Bu nedenle production Vault config içinde `GHCR_USERNAME` ve `GHCR_TOKEN` tutulmalıdır.

## Production Pull-Based Promote

`prod` host GitHub-hosted runner tarafından erişilemiyorsa aşağıdaki model kullanılır:

- GitHub Actions yalnız image build/push yapar.
- `BACKEND_SSH_DEPLOY_ENABLED=false` tutulur.
- Host tarafında `deploy/ubuntu/pull-promote-backend.sh` periyodik veya manuel çalışır.

Ornek manuel promote:

```bash
ENV_FILE=/home/halil/platform/env/backend.env.prod \
DEPLOY_ENV=prod \
VAULT_ADDR=http://127.0.0.1:8200 \
deploy/ubuntu/pull-promote-backend.sh
```

Ornek cron:

```cron
*/5 * * * * cd /home/halil/platform/repo && ENV_FILE=/home/halil/platform/env/backend.env.prod DEPLOY_ENV=prod VAULT_ADDR=http://127.0.0.1:8200 deploy/ubuntu/pull-promote-backend.sh >> /home/halil/platform/state/logs/prod-backend-pull.log 2>&1
```

## Notlar

- Secret değerleri repo'ya commit edilmez.
- Host üzerindeki `backend.env` dosyası Vault kaynaklı tek materialized secret setidir.
- Production `backend.env.prod` dosyası da aynı şekilde Vault render sonucu üretilir.
- `IMAGE_TAG` alanı deploy/rollback sırasında script tarafından güncellenir.
- `backend/scripts/vault/write-backend-deploy-stage.sh` ve `write-backend-deploy-prod.sh` helper script'leri ilgili Vault path'lerini doldurmak için eklendi.
- `deploy-backend.sh`, `RENDER_ENV_BEFORE_DEPLOY=true` verildiğinde deploy öncesi `backend.env` dosyasını Vault'tan otomatik yenileyebilir.
- `RB-ubuntu-backend-github-vault-deploy.md` deploy zincirinin canonical runbook özetidir.
- Production promote/cutover checklist'i:
  - `docs/04-operations/RUNBOOKS/RB-production-cutover-checklist.md`
- Production Vault key matrisi:
  - `docs/OPERATIONS/prod-vault-key-matrix.v1.json`
- Production GitHub environment secret matrisi:
  - `docs/OPERATIONS/prod-github-environment-secret-map.v1.json`
- Production public edge matrisi:
  - `docs/OPERATIONS/prod-public-edge-map.v1.json`
- `ai.acik.com` icin ornek Caddy config:
  - `deploy/ubuntu/Caddyfile.ai-acik.com.example`
- Production backend validate için:
  - `post-deploy-validate.yml` workflow_dispatch `env=prod` ve `target=backend|all`

## Ubuntu Frontend (Nginx)

Bu repo artık Ubuntu üzerinde tek-domain statik frontend bundle'ı da üretebilir.

- Build script:
  - `web/scripts/deploy/build-single-domain.mjs`
- PNPM komutu:
  - `pnpm run build:ubuntu:single-domain`
- Host deploy script:
  - `deploy/ubuntu/deploy-frontend.sh`
- Host rollback script:
  - `deploy/ubuntu/rollback-frontend.sh`
- Containerized Nginx launcher:
  - `deploy/ubuntu/run-frontend-nginx-container.sh`
- Nginx örnek config:
  - `deploy/ubuntu/nginx-frontend-5544.example.conf`
- TLS / live edge için önerilen host:
  - `ai.acik.com`
- `ai.acik.com` için örnek Caddy config:
  - `deploy/ubuntu/Caddyfile.ai-acik.com.example`
- Host prerequisites:
  - `git`
  - `node 20`
  - `pnpm`
  - `docker`

Önerilen host path'leri:

- release klasörü:
  - `/home/halil/platform/web/releases/<git-sha>`
- aktif symlink:
  - `/home/halil/platform/web/current`

Build sırasında tek-domain public origin env'i zorunludur:

```bash
cd web
WEB_PUBLIC_ORIGIN="http://10.9.10.53:5544" pnpm run build:ubuntu:single-domain
```

Host deploy:

```bash
PUBLIC_ORIGIN="http://10.9.10.53:5544" \
REPO_DIR="/home/halil/platform/repo" \
WEB_RELEASES_DIR="/home/halil/platform/web/releases" \
WEB_CURRENT_LINK="/home/halil/platform/web/current" \
deploy/ubuntu/deploy-frontend.sh
```

`deploy-frontend.sh` host üzerinde `pnpm install --frozen-lockfile` çalıştırır; bu yüzden Ubuntu makinede `pnpm` kurulu olmalıdır. `NGINX_CONTAINER_ENABLED=true` ile çağrıldığında aynı akış Docker içindeki Nginx container'ını da yeniler.

HTTPS / secure-context için opsiyonel env desteği:

- `NGINX_SERVER_NAME`
- `NGINX_TLS_ENABLED=true`
- `NGINX_TLS_CERT_PATH`
- `NGINX_TLS_KEY_PATH`
- `NGINX_HTTP_PORT` varsayılan `80`
- `NGINX_HTTPS_PORT` varsayılan `443`

Örnek canlı host çağrısı:

```bash
PUBLIC_ORIGIN="https://ai.acik.com" \
KEYCLOAK_PUBLIC_URL="https://ai.acik.com" \
NGINX_CONTAINER_ENABLED="true" \
NGINX_SERVER_NAME="ai.acik.com" \
NGINX_TLS_ENABLED="true" \
NGINX_TLS_CERT_PATH="/etc/letsencrypt/live/ai.acik.com/fullchain.pem" \
NGINX_TLS_KEY_PATH="/etc/letsencrypt/live/ai.acik.com/privkey.pem" \
NGINX_HTTP_PORT="80" \
NGINX_HTTPS_PORT="443" \
deploy/ubuntu/deploy-frontend.sh
```

Bu akış şu anda çekirdek remote setini paketler:

- `mfe-shell`
- `mfe-users`
- `mfe-access`
- `mfe-audit`
- `mfe-reporting`

`deploy-web.yml` içinde `WEB_DEPLOY_PROVIDER=ubuntu-nginx` ayarlanırsa:

- `stage` için self-hosted runner üstünden host deploy yapılır
- `prod/non-stage` için `WEB_SSH_DEPLOY_ENABLED=true` ise SSH deploy yolu kullanılır

Canlı / secure-context için ek GitHub environment var'ları:

- `WEB_PUBLIC_ORIGIN=https://ai.acik.com`
- `WEB_KEYCLOAK_PUBLIC_URL=https://ai.acik.com`
- `WEB_EDGE_SERVER_NAME=ai.acik.com`
- `WEB_TLS_ENABLED=true`
- `WEB_TLS_CERT_PATH=/etc/letsencrypt/live/ai.acik.com/fullchain.pem`
- `WEB_TLS_KEY_PATH=/etc/letsencrypt/live/ai.acik.com/privkey.pem`
- `WEB_HTTP_PORT=80`
- `WEB_HTTPS_PORT=443`

Stage üzerinde gerçek sertifika henüz yoksa geçici self-signed fallback kullanılabilir:

- `WEB_TLS_SELF_SIGNED=true`
- `WEB_TLS_CERT_PATH=/home/halil/platform/tls/ai.acik.com/fullchain.pem`
- `WEB_TLS_KEY_PATH=/home/halil/platform/tls/ai.acik.com/privkey.pem`

Bu fallback yalnız `deploy-stage-web` self-hosted job'ında, cert dosyaları yoksa `openssl` ile 30 günlük self-signed sertifika üretir. Amaç secure-context açıp stage smoke'u tamamlamaktır; public canlı için yine geçerli CA sertifikası tercih edilmelidir.

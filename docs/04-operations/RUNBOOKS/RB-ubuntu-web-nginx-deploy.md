# RB-ubuntu-web-nginx-deploy – GitHub → Ubuntu Nginx Frontend Akışı

ID: RB-ubuntu-web-nginx-deploy  
Service: web-deploy  
Status: Draft  
Owner: @team/platform

-------------------------------------------------------------------------------
1. AMAÇ
-------------------------------------------------------------------------------

- Frontend'i Cloudflare beklemeden Ubuntu host üzerinde tek-domain olarak yayınlamak.
- Mikrofrontend remote'larını aynı origin altında toplamak.
- `/api` çağrılarını aynı origin üzerinden backend gateway'e reverse proxy etmek.

-------------------------------------------------------------------------------
2. KAPSAM
-------------------------------------------------------------------------------

- Repo: `Halildeu/platform-ssot`
- Runtime target: Ubuntu host + Nginx
- Dış giriş: `:5544`
- Single-domain bundle:
  - shell root altında
  - remote'lar `/remotes/<slug>/remoteEntry.js`

-------------------------------------------------------------------------------
3. CANONICAL DOSYALAR
-------------------------------------------------------------------------------

- Build script:
  - `web/scripts/deploy/build-single-domain.mjs`
- Package script:
  - `web/package.json` → `build:ubuntu:single-domain`
- Host deploy:
  - `deploy/ubuntu/deploy-frontend.sh`
- Host rollback:
  - `deploy/ubuntu/rollback-frontend.sh`
- Nginx örnek config:
  - `deploy/ubuntu/nginx-frontend-5544.example.conf`
- GitHub workflow:
  - `.github/workflows/deploy-web.yml`

-------------------------------------------------------------------------------
4. TOPOLOJİ
-------------------------------------------------------------------------------

Public origin örneği:

- `http://10.9.10.53:5544`

Path map:

- `/` → `mfe-shell`
- `/remoteEntry.js` → shell remote entry
- `/remotes/access/remoteEntry.js` → `mfe-access`
- `/remotes/audit/remoteEntry.js` → `mfe-audit`
- `/remotes/reporting/remoteEntry.js` → `mfe-reporting`
- `/remotes/users/remoteEntry.js` → `mfe-users`
- `/api/*` → `api-gateway`

-------------------------------------------------------------------------------
5. HOST PATH'LERİ
-------------------------------------------------------------------------------

- Gereken host paketleri:
  - `git`
  - `node 20`
  - `pnpm`
  - `nginx`
- Repo checkout:
  - `/home/halil/platform/repo`
- Frontend release klasörü:
  - `/home/halil/platform/web/releases`
- Aktif symlink:
  - `/home/halil/platform/web/current`
- State:
  - `/home/halil/platform/state/web.current-release`
  - `/home/halil/platform/state/web.previous-release`

-------------------------------------------------------------------------------
6. ADIMLAR
-------------------------------------------------------------------------------

### 6.1 Lokal veya CI build

```bash
cd web
WEB_PUBLIC_ORIGIN="http://10.9.10.53:5544" pnpm run build:ubuntu:single-domain
```

### 6.2 Host deploy

```bash
PUBLIC_ORIGIN="http://10.9.10.53:5544" \
REPO_DIR="/home/halil/platform/repo" \
WEB_RELEASES_DIR="/home/halil/platform/web/releases" \
WEB_CURRENT_LINK="/home/halil/platform/web/current" \
deploy/ubuntu/deploy-frontend.sh
```

Not: deploy script host üzerinde `pnpm install --frozen-lockfile` çalıştırır.

### 6.3 Rollback

```bash
WEB_CURRENT_LINK="/home/halil/platform/web/current" \
deploy/ubuntu/rollback-frontend.sh
```

-------------------------------------------------------------------------------
7. GITHUB AKIŞI
-------------------------------------------------------------------------------

`deploy-web.yml` içinde iki yol vardır:

- `WEB_DEPLOY_PROVIDER=hook`
  - mevcut hook tabanlı deploy devam eder
- `WEB_DEPLOY_PROVIDER=ubuntu-nginx`
  - `stage` → self-hosted runner üstünde host deploy
  - `prod/non-stage` → `WEB_SSH_DEPLOY_ENABLED=true` ise SSH deploy

Önerilen GitHub environment var/secrets:

- var:
  - `WEB_DEPLOY_PROVIDER=ubuntu-nginx`
  - `WEB_PUBLIC_ORIGIN=http://10.9.10.53:5544`
  - `WEB_DEPLOY_REMOTE_REPO_DIR=/home/halil/platform/repo`
  - `WEB_DEPLOY_REMOTE_RELEASES_DIR=/home/halil/platform/web/releases`
  - `WEB_DEPLOY_REMOTE_CURRENT_LINK=/home/halil/platform/web/current`
- secret:
  - `WEB_SSH_DEPLOY_ENABLED`
  - `WEB_DEPLOY_SSH_HOST`
  - `WEB_DEPLOY_SSH_PORT`
  - `WEB_DEPLOY_SSH_USER`
  - `WEB_DEPLOY_SSH_KEY`
  - `WEB_DEPLOY_SSH_KNOWN_HOSTS`
  - `WEB_SMOKE_URL`

-------------------------------------------------------------------------------
8. NOTLAR
-------------------------------------------------------------------------------

- Bu ilk sürüm yalnız çekirdek remote setini paketler.
- Cloudflare single-domain topolojisi ayrı bir yol olarak daha sonra eklenebilir.
- `5544` public origin olduğu için auth redirect ve frontend public URL'leri aynı portla tanımlanmalıdır.

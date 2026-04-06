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
3. BAŞLATMA / DURDURMA
-------------------------------------------------------------------------------

### 3.1 Lokal veya CI build

```bash
cd web
WEB_PUBLIC_ORIGIN="http://10.9.10.53:5544" pnpm run build:ubuntu:single-domain
```

### 3.2 Host deploy / yayın alma

```bash
PUBLIC_ORIGIN="http://10.9.10.53:5544" \
REPO_DIR="/home/halil/platform/repo" \
WEB_RELEASES_DIR="/home/halil/platform/web/releases" \
WEB_CURRENT_LINK="/home/halil/platform/web/current" \
NGINX_CONTAINER_ENABLED="true" \
deploy/ubuntu/deploy-frontend.sh
```

Not: deploy script host üzerinde `pnpm install --frozen-lockfile` çalıştırır. `NGINX_CONTAINER_ENABLED=true` verildiğinde 5544 dinleyen Docker Nginx container'ını da yeniler.

### 3.3 Rollback / durdurma

```bash
WEB_CURRENT_LINK="/home/halil/platform/web/current" \
deploy/ubuntu/rollback-frontend.sh
```

Gerekirse Nginx container'ını durdurma:

```bash
docker rm -f platform-web-nginx
```

`deploy-web.yml` içinde iki yol vardır:

- `WEB_DEPLOY_PROVIDER=hook`
  - mevcut hook tabanlı deploy devam eder
- `WEB_DEPLOY_PROVIDER=ubuntu-nginx`
  - `stage` → self-hosted runner üstünde host deploy
  - `prod/non-stage` → `WEB_SSH_DEPLOY_ENABLED=true` ise SSH deploy

-------------------------------------------------------------------------------
4. GÖZLEMLEME / LOG / METRİKLER
-------------------------------------------------------------------------------

- Canonical dosyalar:
  - `web/scripts/deploy/build-single-domain.mjs`
  - `web/package.json` → `build:ubuntu:single-domain`
  - `deploy/ubuntu/deploy-frontend.sh`
  - `deploy/ubuntu/rollback-frontend.sh`
  - `deploy/ubuntu/run-frontend-nginx-container.sh`
  - `deploy/ubuntu/nginx-frontend-5544.example.conf`
  - `.github/workflows/deploy-web.yml`
  - `.github/workflows/post-deploy-validate.yml`
- Topoloji:
  - public origin: `http://10.9.10.53:5544`
  - `/` → `mfe-shell`
  - `/remoteEntry.js` → shell remote entry
  - `/remotes/access/remoteEntry.js` → `mfe-access`
  - `/remotes/audit/remoteEntry.js` → `mfe-audit`
  - `/remotes/reporting/remoteEntry.js` → `mfe-reporting`
  - `/remotes/users/remoteEntry.js` → `mfe-users`
  - `/api/*` → `api-gateway`
- Host path'leri:
  - repo checkout: `/home/halil/platform/repo`
  - release root: `/home/halil/platform/web/releases`
  - aktif symlink: `/home/halil/platform/web/current`
  - state: `/home/halil/platform/state/web.current-release`
  - state: `/home/halil/platform/state/web.previous-release`
- Health / smoke:
  - `http://10.9.10.53:5544/nginx-healthz`
  - `post-deploy-validate.yml` içindeki stage web smoke job'ı
- Log / izleme:
  - GitHub Actions `deploy-web`
  - GitHub Actions `post-deploy-validate`
  - `docker logs platform-web-nginx`

-------------------------------------------------------------------------------
5. ARIZA DURUMLARI VE ADIMLAR
-------------------------------------------------------------------------------

- [ ] Arıza senaryosu 1 – Build artefaktı oluşmuyor:
  - Given: `deploy-web` veya lokal `pnpm run build:ubuntu:single-domain` çalıştırılmıştır.
  - When: single-domain build hata verir veya `web/dist/ubuntu-single-domain` oluşmaz.
  - Then: önce `pnpm install --frozen-lockfile` tekrar çalıştırılır, sonra `WEB_PUBLIC_ORIGIN` değeri doğrulanır ve build yeniden alınır.

- [ ] Arıza senaryosu 2 – Nginx container 5544 üzerinde kalkmıyor:
  - Given: release host üzerinde başarıyla hazırlanmıştır.
  - When: `platform-web-nginx` container'ı çıkış yapar veya `5544` portunu dinlemez.
  - Then: `docker logs platform-web-nginx` ile config hatası kontrol edilir, gerekirse `deploy/ubuntu/run-frontend-nginx-container.sh` yeniden çalıştırılır ve hostta `5544` port çakışması doğrulanır.

- [ ] Arıza senaryosu 3 – Frontend açılıyor ama `/api` istekleri başarısız:
  - Given: tarayıcıdan `:5544` üzerinden shell yüklenmektedir.
  - When: API çağrıları `502/504` döner veya gateway yanıt vermez.
  - Then: backend gateway health durumu kontrol edilir, Nginx upstream hedefi `127.0.0.1:8080` olarak doğrulanır ve gerekirse backend deploy/smoke zinciri yeniden çalıştırılır.

-------------------------------------------------------------------------------
6. ÖZET
-------------------------------------------------------------------------------

- Frontend ilk canlı kesitte Ubuntu üzerinde tek-domain olarak yayınlanır.
- Nginx edge katmanı `5544` portunda statik bundle ve `/api` reverse proxy sağlar.
- Stage deploy zinciri GitHub Actions üzerinden build, host release ve smoke validation adımlarını kapsar.

-------------------------------------------------------------------------------
7. LİNKLER (İSTEĞE BAĞLI)
-------------------------------------------------------------------------------

- RUNBOOK: `docs/04-operations/RUNBOOKS/RB-ubuntu-backend-github-vault-deploy.md`
- RUNBOOK: `docs/04-operations/RUNBOOKS/RB-production-cutover-checklist.md`
- RUNBOOK: `docs/04-operations/RUNBOOKS/RB-web-playwright-smoke.md`
- Workflow: `.github/workflows/deploy-web.yml`
- Workflow: `.github/workflows/post-deploy-validate.yml`
- Monitoring: `docker logs platform-web-nginx`

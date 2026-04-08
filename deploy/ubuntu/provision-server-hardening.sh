#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Production server hardening — run once on fresh Ubuntu server
# See: docs/04-operations/RUNBOOKS/RB-server-hardening-checklist.md
# ---------------------------------------------------------------------------

echo "=== 1. UFW Firewall ==="
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp comment 'SSH'
sudo ufw allow 80/tcp comment 'HTTP redirect to HTTPS'
sudo ufw allow 443/tcp comment 'HTTPS'
sudo ufw --force enable
sudo ufw reload
echo "[OK] UFW configured: 22/80/443 only"

echo "=== 2. Fail2ban ==="
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
echo "[OK] Fail2ban active"

echo "=== 3. Kernel Hardening ==="
sudo tee /etc/sysctl.d/99-hardening.conf > /dev/null <<EOF
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.tcp_syncookies = 1
EOF
sudo sysctl -p /etc/sysctl.d/99-hardening.conf
echo "[OK] Kernel hardened"

echo "=== 4. SSH Hardening Verification ==="
grep -q "^PermitRootLogin no" /etc/ssh/sshd_config && echo "[OK] Root login disabled" || echo "[WARN] PermitRootLogin not set to 'no'"
grep -q "^MaxAuthTries" /etc/ssh/sshd_config && echo "[OK] MaxAuthTries set" || echo "[WARN] MaxAuthTries not configured"

echo "=== 5. TLS Directory ==="
mkdir -p /home/halil/platform/tls/ai.acik.com
echo "[OK] TLS directory ready (copy cert files manually)"

echo "=== 6. SSH 5544 Proxy Cleanup ==="
if pgrep -f ssh_5544_proxy >/dev/null 2>&1; then
  kill "$(pgrep -f ssh_5544_proxy)"
  echo "[OK] SSH 5544 proxy killed"
else
  echo "[OK] SSH 5544 proxy not running"
fi
if crontab -l 2>/dev/null | grep -q ssh_5544_proxy; then
  crontab -l | grep -v ssh_5544_proxy | crontab -
  echo "[OK] SSH 5544 proxy removed from cron"
else
  echo "[OK] SSH 5544 proxy not in cron"
fi

echo "=== 7. OS Updates ==="
sudo apt update && sudo apt upgrade -y
echo "[OK] OS updated"

echo ""
echo "=== PROVISION COMPLETE ==="
echo "Remaining manual steps:"
echo "  1. Copy SSL cert to /home/halil/platform/tls/ai.acik.com/"
echo "  2. Run deploy/ubuntu/run-vault-container.sh"
echo "  3. Run deploy/ubuntu/run-frontend-nginx-container.sh (with NGINX_TLS_ENABLED=true)"
echo "  4. Start backend: docker compose --env-file <env> -f docker-compose.prod.yml up -d"
echo "  5. Start keycloak: cd deploy/ubuntu/keycloak && docker compose up -d"
echo "  6. Verify with: RB-server-hardening-checklist.md section 4"

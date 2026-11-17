#!/usr/bin/env bash
# AirManager — Update / Redeploy Script after `git pull`
# Run from your git repo root on linuxserver (e.g. /home/eddie/apps/airmanager-src/airmanager):
#   git pull && sudo ./deploy/update.sh
set -euo pipefail

INSTALL_DIR="/opt/airmanager"
SERVICE_USER="airmanager"

echo "=== [1/4] Syncing updated repo files to ${INSTALL_DIR} ==="
sudo rsync -a --delete \
  --exclude '.venv' \
  --exclude 'node_modules' \
  --exclude '.next' \
  --exclude '*.db' \
  backend/ "${INSTALL_DIR}/backend/"

sudo rsync -a --delete \
  --exclude '.venv' \
  agent/ "${INSTALL_DIR}/agent/"

sudo rsync -a --delete \
  --exclude 'node_modules' \
  --exclude '.next' \
  frontend/ "${INSTALL_DIR}/frontend/"

sudo cp -R deploy "${INSTALL_DIR}/"

echo "=== [2/4] Fixing PostgreSQL table ownership & updating systemd unit files (ports 8001 & 3002) ==="
sudo -u postgres psql -d airmanager -c "ALTER SCHEMA public OWNER TO airmanager; GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO airmanager; GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO airmanager;"
for tbl in credential_profiles subnets routers devices device_ip_history wireless_clients device_metrics agent_tasks; do
    sudo -u postgres psql -d airmanager -c "ALTER TABLE IF EXISTS ${tbl} OWNER TO airmanager;"
done
for seq in device_ip_history_id_seq device_metrics_id_seq; do
    sudo -u postgres psql -d airmanager -c "ALTER SEQUENCE IF EXISTS ${seq} OWNER TO airmanager;"
done
sudo cp "${INSTALL_DIR}/deploy/systemd/"*.service /etc/systemd/system/
sudo systemctl daemon-reload

echo "=== [3/4] Rebuilding Next.js Frontend (Tailwind CSS + API Proxy to 8001) ==="
sudo chown -R "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}"
cd "${INSTALL_DIR}/frontend"
sudo -u "${SERVICE_USER}" npm run build

echo "=== [4/4] Restarting AirManager services ==="
sudo systemctl restart airmanager-api.service airmanager-agent.service airmanager-web.service
sudo systemctl status airmanager-api.service airmanager-agent.service airmanager-web.service --no-pager

echo "Update complete! Verify at https://ubnt.ahmedadil.me"

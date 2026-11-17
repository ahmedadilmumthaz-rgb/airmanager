#!/usr/bin/env bash
# AirManager v1.0 — Ubuntu 22.04 / 24.04 LTS Native Bare-Metal Installer (No Docker)
set -euo pipefail

INSTALL_DIR="/opt/airmanager"
ENV_DIR="/etc/airmanager"
SERVICE_USER="airmanager"

echo "=== [1/7] Installing Ubuntu system dependencies (PostgreSQL, Python 3, Node.js, Nginx) ==="
sudo apt-get update -y
sudo apt-get install -y postgresql postgresql-contrib python3 python3-venv python3-pip nginx nodejs npm openssl

echo "=== [2/7] Creating system user & directories ==="
if ! id -u "${SERVICE_USER}" >/dev/null 2>&1; then
    sudo useradd --system --home "${INSTALL_DIR}" --shell /usr/sbin/nologin "${SERVICE_USER}"
fi
sudo mkdir -p "${INSTALL_DIR}" "${ENV_DIR}"
sudo cp -R backend agent frontend deploy "${INSTALL_DIR}/"

echo "=== [3/7] Provisioning PostgreSQL database and schema ==="
DB_PASS="$(openssl rand -hex 16)"
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='airmanager'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER airmanager WITH PASSWORD '${DB_PASS}';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='airmanager'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE airmanager OWNER airmanager;"
sudo -u postgres psql -d airmanager -f "${INSTALL_DIR}/deploy/sql/001_initial_schema.sql"

echo "=== [4/7] Generating /etc/airmanager/airmanager.env ==="
if [ ! -f "${ENV_DIR}/airmanager.env" ]; then
    MASTER_KEY="$(openssl rand -base64 32)"
    AGENT_TOKEN="$(openssl rand -hex 24)"
    sudo tee "${ENV_DIR}/airmanager.env" >/dev/null <<EOF
AIRMANAGER_DATABASE_URL=postgresql+psycopg2://airmanager:${DB_PASS}@127.0.0.1:5432/airmanager
AIRMANAGER_MASTER_KEY=${MASTER_KEY}
AIRMANAGER_AGENT_TOKEN=${AGENT_TOKEN}
AIRMANAGER_ADMIN_USER=admin
AIRMANAGER_ADMIN_PASSWORD=ubnt-admin-change-me
AIRMANAGER_AUTO_SEED=false
AIRMANAGER_BACKEND_URL=http://127.0.0.1:8001
AIRMANAGER_CORS_ORIGINS=http://localhost:3002,http://127.0.0.1:3002,https://airmanager.ahmedadil.me
AIRMANAGER_SCAN_CONCURRENCY=64
AIRMANAGER_POLL_INTERVAL_SEC=20
EOF
    sudo chown "${SERVICE_USER}:${SERVICE_USER}" "${ENV_DIR}/airmanager.env"
    sudo chmod 0600 "${ENV_DIR}/airmanager.env"
fi

echo "=== [5/7] Setting up Python virtual environments for Backend & Agent ==="
python3 -m venv "${INSTALL_DIR}/backend/.venv"
"${INSTALL_DIR}/backend/.venv/bin/pip" install --upgrade pip
"${INSTALL_DIR}/backend/.venv/bin/pip" install -r "${INSTALL_DIR}/backend/requirements.txt"

python3 -m venv "${INSTALL_DIR}/agent/.venv"
"${INSTALL_DIR}/agent/.venv/bin/pip" install --upgrade pip
"${INSTALL_DIR}/agent/.venv/bin/pip" install -r "${INSTALL_DIR}/agent/requirements.txt"

echo "=== [6/7] Building Next.js TypeScript Frontend ==="
cd "${INSTALL_DIR}/frontend"
npm install
npm run build

sudo chown -R "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}"

echo "=== [7/7] Enabling systemd services & Nginx reverse proxy ==="
sudo cp "${INSTALL_DIR}/deploy/systemd/"*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now airmanager-api.service airmanager-agent.service airmanager-web.service

sudo cp "${INSTALL_DIR}/deploy/nginx/airmanager.conf" /etc/nginx/sites-available/airmanager.conf
sudo ln -sf /etc/nginx/sites-available/airmanager.conf /etc/nginx/sites-enabled/airmanager.conf
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

echo "AirManager v1.0 successfully installed and running!"

# AirManager v1.0 — Ubuntu Linux Server Deployment Guide (No Docker)

This guide walks through deploying **AirManager** on a bare-metal or VM **Ubuntu 22.04 LTS / 24.04 LTS** server with routed IPv4 connectivity to your Ubiquiti **airOS 8** subnets (`LiteAP GPS` sectors and `NanoStation Loco 5AC` stations).

---

## 1. Server Requirements & Network Prerequisites

### 1.1 Hardware Sizing (30–100 Radios)
| Resource | Minimum | Recommended |
| :--- | :--- | :--- |
| **OS** | Ubuntu 22.04 LTS (64-bit) | Ubuntu 24.04 LTS (64-bit) |
| **CPU** | 2 vCPU | 4 vCPU |
| **RAM** | 2 GB | 4 GB |
| **Disk** | 20 GB SSD | 40 GB NVMe SSD (PostgreSQL telemetry retention) |

### 1.2 Multi-Subnet Routing & Firewall Checklist
Because AirManager uses **routed CIDR scanning** instead of Layer-2 UDP broadcast discovery, verify that your Linux server has IPv4 routes to every radio management subnet:

```bash
# 1. Verify kernel routing table reaches your radio management subnets
ip route show
ip route get 10.10.10.11   # Example LiteAP GPS sector IP
ip route get 172.16.40.11  # Example remote routed sector IP

# 2. Verify HTTPS (443) reachability to a sample airOS 8 radio
nc -zv -w 2 10.10.10.11 443
```

**Firewall Rules (`ufw`)**:
- **Inbound to Ubuntu Server**:
  - `22/tcp` (SSH administration)
  - `80/tcp` and `443/tcp` (Nginx Web UI & REST API)
- **Outbound from Ubuntu Server (`airmanager-agent`)**:
  - `443/tcp` and `80/tcp` to all configured radio management CIDRs (`LiteAP GPS` & `Loco 5AC`)
  - `22/tcp` (SSH) or `443/tcp` (HTTPS) to optional Ubiquiti EdgeRouter / UISP gateways for ARP & DHCP lease enrichment

---

## 2. Option A: Automated Installation (`deploy/install.sh`)

If you are deploying all components (PostgreSQL, FastAPI Backend, Linux Network Agent, Next.js Frontend, and Nginx) onto a single Ubuntu server:

### Step 1: Copy Project to the Ubuntu Server
From your workstation:
```bash
rsync -avz --exclude '.git' --exclude 'node_modules' --exclude '.venv' \
  ./ ubuntu@<SERVER_IP>:/tmp/airmanager-src/
```

### Step 2: Run the Installer Script
SSH into the Ubuntu server and execute [install.sh](file:///Users/ahmedadil/Downloads/untitled%20folder/ubiquiti/deploy/install.sh):
```bash
ssh ubuntu@<SERVER_IP>
cd /tmp/airmanager-src
chmod +x deploy/install.sh
sudo ./deploy/install.sh
```

What `install.sh` does automatically:
1. Installs `postgresql`, `python3-venv`, `python3-pip`, `nodejs`, `npm`, `nginx`, and `openssl`.
2. Creates a dedicated unprivileged system user `airmanager` with home `/opt/airmanager`.
3. Creates the PostgreSQL user `airmanager`, database `airmanager`, and applies [001_initial_schema.sql](file:///Users/ahmedadil/Downloads/untitled%20folder/ubiquiti/deploy/sql/001_initial_schema.sql).
4. Generates cryptographic secrets (`AIRMANAGER_MASTER_KEY` and `AIRMANAGER_AGENT_TOKEN`) in `/etc/airmanager/airmanager.env` with `0600` permissions.
5. Builds isolated Python virtualenvs (`/opt/airmanager/backend/.venv` and `/opt/airmanager/agent/.venv`).
6. Compiles the Next.js production bundle (`/opt/airmanager/frontend/.next`).
7. Installs and starts `airmanager-api.service`, `airmanager-agent.service`, `airmanager-web.service`, and reloads `nginx`.

---

## 3. Option B: Step-by-Step Manual Deployment

Use this walkthrough if you want full manual control over each step or are separating the Linux Agent onto a dedicated routing probe box.

### Step 1: Install System Packages
```bash
sudo apt-get update -y
sudo apt-get install -y postgresql postgresql-contrib python3 python3-venv python3-pip nginx curl openssl

# If Ubuntu's default nodejs is older than v18, install Node.js 20 LTS:
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### Step 2: Create System User & Copy Application Files
```bash
sudo useradd --system --home /opt/airmanager --shell /usr/sbin/nologin airmanager || true
sudo mkdir -p /opt/airmanager /etc/airmanager
sudo cp -R backend agent frontend deploy /opt/airmanager/
```

### Step 3: Configure PostgreSQL 16 Database
```bash
# Generate a strong database password
DB_PASS="$(openssl rand -hex 16)"
echo "Generated DB Password: ${DB_PASS}"

sudo -u postgres psql <<EOF
CREATE USER airmanager WITH PASSWORD '${DB_PASS}';
CREATE DATABASE airmanager OWNER airmanager;
\c airmanager
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
EOF

# Apply the initial schema
sudo -u postgres psql -d airmanager -f /opt/airmanager/deploy/sql/001_initial_schema.sql
```

### Step 4: Create `/etc/airmanager/airmanager.env`
Generate your Fernet master encryption key (used to encrypt airOS 8 and router passwords at rest) and shared agent token:

```bash
MASTER_KEY="$(openssl rand -base64 32)"
AGENT_TOKEN="$(openssl rand -hex 24)"

sudo tee /etc/airmanager/airmanager.env >/dev/null <<EOF
# PostgreSQL Connection
AIRMANAGER_DATABASE_URL=postgresql+psycopg2://airmanager:${DB_PASS}@127.0.0.1:5432/airmanager

# Security & Encryption
AIRMANAGER_MASTER_KEY=${MASTER_KEY}
AIRMANAGER_AGENT_TOKEN=${AGENT_TOKEN}
AIRMANAGER_ADMIN_USER=admin
AIRMANAGER_ADMIN_PASSWORD=ChangeMe-StrongPassword-2026!

# Production Mode (set false so demo data is not seeded into production)
AIRMANAGER_AUTO_SEED=false

# Linux Network Agent Settings
AIRMANAGER_BACKEND_URL=http://127.0.0.1:8000
AIRMANAGER_SCAN_CONCURRENCY=64
AIRMANAGER_TCP_TIMEOUT_SEC=1.5
AIRMANAGER_POLL_INTERVAL_SEC=20
AIRMANAGER_SIMULATOR_MODE=false
EOF

sudo chown airmanager:airmanager /etc/airmanager/airmanager.env
sudo chmod 0600 /etc/airmanager/airmanager.env
```

### Step 5: Set Up Python Virtual Environments
```bash
# Central FastAPI Backend
python3 -m venv /opt/airmanager/backend/.venv
/opt/airmanager/backend/.venv/bin/pip install --upgrade pip
/opt/airmanager/backend/.venv/bin/pip install -r /opt/airmanager/backend/requirements.txt

# Linux Multi-Subnet Network Agent
python3 -m venv /opt/airmanager/agent/.venv
/opt/airmanager/agent/.venv/bin/pip install --upgrade pip
/opt/airmanager/agent/.venv/bin/pip install -r /opt/airmanager/agent/requirements.txt
```

### Step 6: Build the Next.js + TypeScript Frontend
```bash
cd /opt/airmanager/frontend
npm install
npm run build
sudo chown -R airmanager:airmanager /opt/airmanager
```

### Step 7: Install & Start `systemd` Services
Copy the unit files from [deploy/systemd/](file:///Users/ahmedadil/Downloads/untitled%20folder/ubiquiti/deploy/systemd/airmanager-api.service) and enable them:

```bash
sudo cp /opt/airmanager/deploy/systemd/airmanager-api.service /etc/systemd/system/
sudo cp /opt/airmanager/deploy/systemd/airmanager-agent.service /etc/systemd/system/
sudo cp /opt/airmanager/deploy/systemd/airmanager-web.service /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now airmanager-api.service
sudo systemctl enable --now airmanager-agent.service
sudo systemctl enable --now airmanager-web.service
```

Verify all three services are `active (running)`:
```bash
sudo systemctl status airmanager-api airmanager-agent airmanager-web
```

### Step 8: Configure Nginx Reverse Proxy & HTTPS
```bash
sudo cp /opt/airmanager/deploy/nginx/airmanager.conf /etc/nginx/sites-available/airmanager.conf
sudo ln -sf /etc/nginx/sites-available/airmanager.conf /etc/nginx/sites-enabled/airmanager.conf
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

#### Adding TLS (HTTPS)
- **Internal WISP Management Network (Self-Signed or Internal CA)**:
  ```bash
  sudo mkdir -p /etc/ssl/airmanager
  sudo openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
    -keyout /etc/ssl/airmanager/privkey.pem \
    -out /etc/ssl/airmanager/fullchain.pem \
    -subj "/CN=airmanager.local"
  ```
  Then uncomment the `listen 443 ssl http2;` and `ssl_certificate` lines in `/etc/nginx/sites-available/airmanager.conf` and run `sudo systemctl reload nginx`.
- **Public FQDN (Let's Encrypt)**:
  ```bash
  sudo apt-get install -y certbot python3-certbot-nginx
  sudo certbot --nginx -d netmgr.yourdomain.com
  ```

---

## 4. Configuring Optional Ubiquiti Router SSH Access (EdgeRouter)

To let `airmanager-agent` harvest ARP and DHCP lease tables from a Ubiquiti EdgeRouter (`show arp` and `show dhcp leases`) so radios that change IP across subnets are immediately tracked by MAC address:

1. Generate an SSH keypair for the `airmanager` service user on Ubuntu:
   ```bash
   sudo -u airmanager mkdir -p /opt/airmanager/.ssh
   sudo -u airmanager ssh-keygen -t ed25519 -N "" -f /opt/airmanager/.ssh/id_ed25519
   ```
2. Add `/opt/airmanager/.ssh/id_ed25519.pub` to your EdgeRouter read-only operator user:
   ```bash
   # On the EdgeRouter CLI:
   configure
   set system login user netops authentication public-keys airmanager type ssh-ed25519
   set system login user netops authentication public-keys airmanager key "<BASE64_KEY>"
   commit ; save
   ```
3. Test passwordless neighbor lookup from the Ubuntu server:
   ```bash
   sudo -u airmanager ssh netops@10.10.10.1 "/opt/vyatta/bin/vyatta-op-cmd-wrapper show arp"
   ```

---

## 5. Post-Deployment Onboarding Checklist

1. **Open the Web Console**: Navigate to `http://<SERVER_IP>/discovery` (or `https://...`).
2. **Add airOS 8 Credentials**:
   - Create your default **airOS 8** credential profile (username & password used on your `LiteAP GPS` and `Loco 5AC` radios). The password is encrypted immediately using `AIRMANAGER_MASTER_KEY`.
3. **Add Routed Subnets**:
   - Add each management CIDR (e.g., `10.10.10.0/24`, `10.10.20.0/24`, `172.16.40.0/24`) and click **Scan Subnet Now**.
4. **Verify Connected Clients**:
   - Open `/clients` (**Connected Client Management**) to view all discovered `LiteAP GPS` sectors and associated `Loco 5AC` stations, filter by weak signal (`< -72 dBm`) or chain imbalance (`≥ 5 dB`), and test **Kick**, **Block/Unblock MAC**, and **Reboot**.

---

## 6. Day-2 Operations, Logs & Backups

### Viewing Live Logs
```bash
# Backend API logs
sudo journalctl -u airmanager-api -f

# Linux Multi-Subnet Agent discovery & polling logs
sudo journalctl -u airmanager-agent -f

# Next.js Web UI logs
sudo journalctl -u airmanager-web -f
```

### Automated Nightly PostgreSQL Backup
Create `/etc/cron.daily/airmanager-backup`:
```bash
sudo tee /etc/cron.daily/airmanager-backup >/dev/null <<'EOF'
#!/usr/bin/env bash
BACKUP_DIR="/var/backups/airmanager"
mkdir -p "${BACKUP_DIR}"
sudo -u postgres pg_dump airmanager | gzip > "${BACKUP_DIR}/airmanager_$(date +%F).sql.gz"
find "${BACKUP_DIR}" -type f -name "*.sql.gz" -mtime +14 -delete
EOF
sudo chmod +x /etc/cron.daily/airmanager-backup
```

### Database Schema Upgrades (Alembic)
When deploying future schema migrations:
```bash
cd /opt/airmanager/backend
sudo -E -u airmanager /opt/airmanager/backend/.venv/bin/alembic upgrade head
sudo systemctl restart airmanager-api airmanager-agent
```

# AirManager v1.0 — Ubuntu Linux Server Deployment Guide (`linuxserver` + Cloudflare Zero Trust Tunnel)

This guide covers deploying **AirManager** on `eddie@linuxserver` (`192.168.11.39`) using:
- **Frontend Port**: `127.0.0.1:3002`
- **Backend API Port**: `127.0.0.1:8001`
- **External Access & HTTPS**: **Cloudflare Zero Trust Tunnel** on `*.ahmedadil.me` (e.g. `https://airmanager.ahmedadil.me`)

---

## 1. Architecture with Cloudflare Zero Trust Tunnel

Because the Frontend server (`127.0.0.1:3002`) automatically proxies all `/api/v1/*` requests internally to the Backend API (`127.0.0.1:8001`), **you only need a single Cloudflare Tunnel Public Hostname pointing to `http://127.0.0.1:3002`**—and you do not need to free up ports `80`, `443`, `3000`, or `8000` on `linuxserver`.

```text
Browser (https://airmanager.ahmedadil.me)
   │
   ▼  (Cloudflare Edge TLS + Zero Trust Access)
cloudflared daemon on linuxserver
   │
   ▼  http://127.0.0.1:3002
airmanager-web.service (Port 3002)
   ├── Serves UI Pages (/ , /clients, /devices, /discovery, /tasks)
   └── Proxies /api/v1/* ──► airmanager-api.service (http://127.0.0.1:8001)
                                 ├── PostgreSQL (127.0.0.1:5432)
                                 └── airmanager-agent.service (Routed airOS 8 Scanner & Poller)
                                       ├── HTTP :80 / SSH :22 ──► 10.61.200.0/24 (NEL1006, etc.)
                                       ├── HTTP :80 / SSH :22 ──► 10.42.200.0/24 (BUDDIESNET6 Sector)
                                       └── HTTP :80 / SSH :22 ──► 172.22.61.0/24
```

---

## 2. Configure Cloudflare Zero Trust Tunnel (`*.ahmedadil.me`)

Since your `linuxserver` tunnel is already active:

### Option A: Via Cloudflare Zero Trust Dashboard (Remotely Managed Tunnel)
1. Go to **Cloudflare One / Zero Trust Dashboard** → **Networks** → **Tunnels**.
2. Click your **`linuxserver`** tunnel → **Configure** → **Public Hostname** tab → **Add a public hostname**:
   - **Subdomain**: `airmanager` *(or `ubnt`, `netmgr`, etc.)*
   - **Domain**: `ahmedadil.me`
   - **Path**: *(leave blank)*
   - **Service Type**: `HTTP`
   - **URL**: `127.0.0.1:3002`
3. Click **Save hostname**. Your app is immediately routed at `https://airmanager.ahmedadil.me`.

*(Optional: If you want `/api/*` routed directly by `cloudflared` to `8001` in addition to the built-in Next.js proxy, you can add a second hostname rule for `airmanager.ahmedadil.me` with **Path** `api/*` → `http://127.0.0.1:8001`, placed above the catch-all rule.)*

### Option B: Via Local `/etc/cloudflared/config.yml` (Locally Managed Tunnel)
If your tunnel uses a local config file on `linuxserver`, add the ingress rule above your fallback `http_status:404`:
```yaml
ingress:
  - hostname: airmanager.ahmedadil.me
    service: http://127.0.0.1:3002
  - service: http_status:404
```
Then reload `cloudflared`:
```bash
sudo systemctl restart cloudflared
```

---

## 3. Deploy or Update Services on `eddie@linuxserver`

### Step 1: Update `/etc/airmanager/airmanager.env`
Ensure `/etc/airmanager/airmanager.env` uses port `8001` and includes your `*.ahmedadil.me` domain:

```bash
sudo tee -a /etc/airmanager/airmanager.env >/dev/null <<'EOF'
PORT=8001
AIRMANAGER_BACKEND_URL=http://127.0.0.1:8001
AIRMANAGER_CORS_ORIGINS=http://localhost:3002,http://127.0.0.1:3002,https://airmanager.ahmedadil.me
NEXT_PUBLIC_API_URL=
EOF
```
*(Keeping `NEXT_PUBLIC_API_URL=` empty ensures the browser always calls relative `/api/v1/*` on `https://airmanager.ahmedadil.me`, which `127.0.0.1:3002` proxies internally to `127.0.0.1:8001`.)*

### Step 2: Update `systemd` Unit Files (`8001` & `3002`)

1. **Backend Service (`/etc/systemd/system/airmanager-api.service`)**:
   ```ini
   [Unit]
   Description=AirManager Central FastAPI Backend Service (Port 8001)
   After=network-online.target postgresql.service
   Wants=network-online.target
   Requires=postgresql.service

   [Service]
   Type=simple
   User=airmanager
   Group=airmanager
   WorkingDirectory=/opt/airmanager/backend
   EnvironmentFile=/etc/airmanager/airmanager.env
   ExecStart=/opt/airmanager/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001 --workers 2
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

2. **Frontend Service (`/etc/systemd/system/airmanager-web.service`)**:
   ```ini
   [Unit]
   Description=AirManager Next.js Operator Console Frontend (Port 3002)
   After=network-online.target airmanager-api.service
   Wants=network-online.target

   [Service]
   Type=simple
   User=airmanager
   Group=airmanager
   WorkingDirectory=/opt/airmanager/frontend
   EnvironmentFile=/etc/airmanager/airmanager.env
   Environment=NODE_ENV=production
   Environment=PORT=3002
   Environment=API_PORT=8001
   ExecStart=/usr/bin/npm run start -- -p 3002 -H 127.0.0.1
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

3. **Linux Agent Service (`/etc/systemd/system/airmanager-agent.service`)**:
   ```ini
   [Unit]
   Description=AirManager Linux Multi-Subnet Network Discovery & airOS 8 Agent
   After=network-online.target airmanager-api.service
   Wants=network-online.target

   [Service]
   Type=simple
   User=airmanager
   Group=airmanager
   WorkingDirectory=/opt/airmanager/agent
   EnvironmentFile=/etc/airmanager/airmanager.env
   ExecStart=/opt/airmanager/agent/.venv/bin/python -m airmanager_agent.main
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

### Step 3: Rebuild Frontend & Restart Services
Because Next.js bakes `rewrites()` (`http://127.0.0.1:8001`) at build time, rebuild the frontend after changing `next.config.mjs` and restart the services:

```bash
cd /opt/airmanager/frontend
sudo -u airmanager npm run build

sudo systemctl daemon-reload
sudo systemctl restart airmanager-api airmanager-agent airmanager-web
```

### Step 4: Verify Ports `8001` & `3002` on `eddie@linuxserver`
```bash
# 1. Verify Backend API on 8001
curl -s http://127.0.0.1:8001/api/v1/health

# 2. Verify Frontend + API proxy on 3002
curl -s http://127.0.0.1:3002/api/v1/health
```

Both commands should return `{"status": "ok", "service": "AirManager (Ubiquiti Network Manager)", ...}`, and you can open `https://<your-subdomain>.ahmedadil.me` from anywhere!

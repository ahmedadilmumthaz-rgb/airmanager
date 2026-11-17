# AirManager (Ubiquiti Network Manager) — Final Implementation Specification v1.0

## 1. Executive Summary & Architectural Decisions

**Project Name**: AirManager (working name: Ubiquiti Network Manager)  
**Target Scale**: 30–100 radios across multiple routed IPv4 subnets  
**Target Hardware & Firmware**: Ubiquiti airMAX AC running **airOS 8** (`LiteAP GPS` Access Points and `NanoStation Loco 5AC` Client Stations)

| Decision Area | Final Selection | Architectural Rationale |
| :--- | :--- | :--- |
| **Network Agent OS** | Linux (`asyncio` daemon) | Native raw/TCP socket concurrency, systemd supervision, zero container overhead |
| **Network Topology** | Multiple routed subnets | Avoids UDP layer-2 broadcast discovery (`10001/udp`); uses routed CIDR scanning + router ARP/DHCP enrichment |
| **Router Infrastructure** | Ubiquiti (EdgeOS / UniFi / UISP) | Pluggable neighbor enrichment via EdgeRouter SSH CLI (`show arp`, `show dhcp leases`) and UniFi/UISP REST APIs |
| **Radio Firmware** | airOS 8 | Uses airOS 8 HTTPS session API (`/api/auth`, `/status.cgi`, `/sta.cgi`, `/kick.cgi`, `/cfg.cgi`, `/reboot.cgi`) |
| **Device Coverage** | `LiteAP GPS` & `Loco 5AC` | Sector APs (`ap-ptmp`) and client CPE stations (`sta-ptmp`) |
| **Initial Priority** | Connected Client Management | Live station health, dual-chain signal analysis, station kick/reconnect, MAC ACL block/unblock, CPE reboot |
| **Central Backend** | FastAPI (Python) | High-throughput async REST + SSE streaming + Pydantic v2 validation + SQLAlchemy 2.0 ORM |
| **Frontend** | Next.js + TypeScript (Tailwind CSS) | Strongly typed operator console with real-time client telemetry, link drawers, and discovery controls |
| **Database** | PostgreSQL 16 | Native `MACADDR`, `INET`, `CIDR`, and `JSONB` types with time-series indexing |
| **Deployment** | Ubuntu 22.04 / 24.04 LTS (No Docker) | Bare-metal `systemd` services (`airmanager-api`, `airmanager-agent`, `airmanager-web`) behind Nginx |

---

## 2. Multi-Subnet Discovery & Identity Architecture

Because the Linux Network Agent connects across **multiple routed subnets**, Layer-2 UDP broadcast discovery (`255.255.255.255:10001`) will not traverse routers. AirManager implements a **5-stage Hybrid Discovery Engine**:

1. **Configured Subnet Scanning**:
   - Iterates over operator-configured IPv4 CIDR blocks (e.g., `10.10.10.0/24`, `10.10.20.0/24`, `172.16.5.0/24`).
   - Performs bounded-concurrency (`asyncio.Semaphore(64)`) TCP handshakes on port `443` (fallback `80`) with a `1.5s` connect timeout.
2. **airOS 8 HTTPS Probing & Fingerprinting**:
   - Connects via TLS (allowing self-signed radio certificates) to candidate hosts.
   - Authenticates against `POST /api/auth` using assigned or default credential profiles, capturing `AIROS_SESSIONID` and `X-CSRF-ID`.
   - Queries `GET /status.cgi` to validate Ubiquiti airOS 8 structure and extract hardware model (`LiteAP GPS`, `Loco 5AC`), firmware (`WA.v8.7.x` / `XC.v8.7.x`), wireless mode, SSID, frequency, GPS coordinates, and interface MACs.
3. **Permanent MAC-Based Canonical Identity**:
   - Every device is uniquely identified by its primary wireless/management `mac_address` (`MACADDR`).
   - If a radio's IP changes (due to DHCP renewal or subnet migration), its existing `devices` record is updated in place (`current_ip`) and a new transition record is written to `device_ip_history`.
4. **Optional Ubiquiti Router Neighbor Enrichment**:
   - Queries configured Ubiquiti routers (EdgeRouter via SSH `show arp` / `show dhcp leases`, or UISP/UniFi API) to harvest `(mac_address, ip_address, vlan)` mappings.
   - Immediately queues newly observed IPs or relocated MACs for airOS probing, even before the next full CIDR scan cycle.
5. **Periodic Station & Telemetry Polling**:
   - Registered `LiteAP GPS` APs are polled every 15–30 seconds via `/status.cgi` and `/sta.cgi`.
   - Every associated `Loco 5AC` client reported in `/sta.cgi` is upserted into `wireless_clients`, cross-linked to `devices` if directly managed, and its `lastip` is queued for direct CPE management probing.

---

## 3. PostgreSQL Database Schema

### 3.1 Complete DDL Specification (`deploy/sql/001_initial_schema.sql`)

```sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Encrypted Credential Vault
CREATE TABLE credential_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(120) NOT NULL UNIQUE,
    username VARCHAR(120) NOT NULL,
    encrypted_password BYTEA NOT NULL,
    https_port INTEGER NOT NULL DEFAULT 443,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Routed Subnets Configuration
CREATE TABLE subnets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cidr_block VARCHAR(43) NOT NULL UNIQUE, -- Stored as canonical CIDR string / PG CIDR compatible
    name VARCHAR(120) NOT NULL,
    site_name VARCHAR(120),
    vlan_id INTEGER,
    scan_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    scan_interval_sec INTEGER NOT NULL DEFAULT 300,
    default_credential_id UUID REFERENCES credential_profiles(id) ON DELETE SET NULL,
    last_scanned_at TIMESTAMPTZ,
    last_discovered_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Optional Ubiquiti Routers for ARP / DHCP Enrichment
CREATE TABLE routers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(120) NOT NULL,
    host_ip VARCHAR(45) NOT NULL UNIQUE,
    router_type VARCHAR(32) NOT NULL CHECK (router_type IN ('edgerouter', 'unifi', 'uisp')),
    port INTEGER NOT NULL DEFAULT 22,
    credential_id UUID REFERENCES credential_profiles(id) ON DELETE SET NULL,
    api_token_encrypted BYTEA,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    last_synced_at TIMESTAMPTZ,
    last_sync_status VARCHAR(64) DEFAULT 'never',
    neighbors_found INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Canonical Radio Registry (LiteAP GPS & Loco 5AC)
CREATE TABLE devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mac_address VARCHAR(17) NOT NULL UNIQUE, -- Normalized uppercase AA:BB:CC:DD:EE:FF
    current_ip VARCHAR(45) NOT NULL,
    hostname VARCHAR(255) NOT NULL,
    model VARCHAR(64) NOT NULL,              -- 'LiteAP GPS', 'Loco 5AC', etc.
    product_code VARCHAR(32),                -- 'LAP-GPS', 'NS-5ACL'
    role VARCHAR(24) NOT NULL CHECK (role IN ('ap', 'station', 'unknown')),
    ssid VARCHAR(128),
    firmware_version VARCHAR(64),
    frequency_mhz INTEGER,
    channel_width_mhz INTEGER,
    tx_power_dbm INTEGER,
    noise_floor_dbm INTEGER,
    cpu_load_pct REAL DEFAULT 0,
    memory_used_pct REAL DEFAULT 0,
    uptime_sec BIGINT DEFAULT 0,
    gps_lat DOUBLE PRECISION,
    gps_lon DOUBLE PRECISION,
    status VARCHAR(24) NOT NULL DEFAULT 'online'
        CHECK (status IN ('online', 'degraded', 'unreachable', 'auth_failed')),
    credential_id UUID REFERENCES credential_profiles(id) ON DELETE SET NULL,
    subnet_id UUID REFERENCES subnets(id) ON DELETE SET NULL,
    first_discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_devices_role_status ON devices(role, status);
CREATE INDEX idx_devices_current_ip ON devices(current_ip);

-- 5. Historical IP Tracking Across Subnets
CREATE TABLE device_ip_history (
    id BIGSERIAL PRIMARY KEY,
    device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    ip_address VARCHAR(45) NOT NULL,
    subnet_cidr VARCHAR(43),
    discovery_source VARCHAR(32) NOT NULL
        CHECK (discovery_source IN ('subnet_scan', 'router_arp', 'router_dhcp', 'station_table', 'manual')),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_device_ip_history_device ON device_ip_history(device_id, last_seen_at DESC);

-- 6. Connected Wireless Clients (Primary Management Scope)
CREATE TABLE wireless_clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ap_device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    client_device_id UUID REFERENCES devices(id) ON DELETE SET NULL,
    client_mac VARCHAR(17) NOT NULL UNIQUE,
    last_known_ip VARCHAR(45),
    remote_hostname VARCHAR(255),
    remote_model VARCHAR(64) DEFAULT 'Loco 5AC',
    remote_firmware VARCHAR(64),
    is_connected BOOLEAN NOT NULL DEFAULT TRUE,
    is_blocked BOOLEAN NOT NULL DEFAULT FALSE,
    signal_dbm INTEGER,
    remote_signal_dbm INTEGER,
    chain0_dbm INTEGER,
    chain1_dbm INTEGER,
    chain_imbalance_db INTEGER GENERATED ALWAYS AS (ABS(COALESCE(chain0_dbm, 0) - COALESCE(chain1_dbm, 0))) STORED,
    noise_floor_dbm INTEGER,
    snr_db INTEGER,
    tx_rate_mbps REAL,
    rx_rate_mbps REAL,
    airmax_capacity_pct INTEGER,
    airmax_quality_pct INTEGER,
    distance_meters INTEGER,
    connection_uptime_sec BIGINT DEFAULT 0,
    tx_bytes BIGINT DEFAULT 0,
    rx_bytes BIGINT DEFAULT 0,
    tx_throughput_kbps REAL DEFAULT 0,
    rx_throughput_kbps REAL DEFAULT 0,
    tx_latency_ms REAL DEFAULT 0,
    first_associated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_wireless_clients_ap ON wireless_clients(ap_device_id);
CREATE INDEX idx_wireless_clients_connected ON wireless_clients(is_connected, signal_dbm);

-- 7. Device & Sector Telemetry Time-Series
CREATE TABLE device_metrics (
    id BIGSERIAL PRIMARY KEY,
    device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cpu_load_pct REAL,
    memory_used_pct REAL,
    connected_clients_count INTEGER DEFAULT 0,
    tx_throughput_kbps REAL DEFAULT 0,
    rx_throughput_kbps REAL DEFAULT 0,
    avg_client_signal_dbm INTEGER,
    noise_floor_dbm INTEGER
);

CREATE INDEX idx_device_metrics_device_time ON device_metrics(device_id, recorded_at DESC);

-- 8. Agent Command Queue & Audit Log
CREATE TABLE agent_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type VARCHAR(48) NOT NULL
        CHECK (task_type IN (
            'scan_subnet',
            'probe_device',
            'kick_client',
            'block_client',
            'unblock_client',
            'reboot_device',
            'sync_router'
        )),
    target_device_id UUID REFERENCES devices(id) ON DELETE SET NULL,
    target_client_id UUID REFERENCES wireless_clients(id) ON DELETE SET NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(24) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    result JSONB,
    error_message TEXT,
    requested_by VARCHAR(120) NOT NULL DEFAULT 'admin',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_agent_tasks_status ON agent_tasks(status, created_at ASC);
```

---

## 4. REST API & Agent Protocol Contracts

### 4.1 Agent Protocol (`/api/v1/agent/*`)
Authenticated with header `X-Agent-Token: <shared-secret>`.

1. **`POST /api/v1/agent/heartbeat`**
   - **Request**:
     ```json
     {
       "agent_id": "ubuntu-net-agent-01",
       "hostname": "netmgr-ubuntu",
       "version": "1.0.0",
       "active_workers": 4,
       "simulator_mode": false
     }
     ```
   - **Response**:
     ```json
     {
       "server_time": "2026-11-17T21:30:00Z",
       "pending_tasks": [
         {
           "id": "uuid",
           "task_type": "kick_client",
           "payload": {
             "ap_ip": "10.10.10.11",
             "ap_mac": "78:8A:20:41:10:01",
             "client_mac": "78:8A:20:88:A1:05"
           }
         }
       ],
       "subnets": [...],
       "routers": [...]
     }
     ```

2. **`POST /api/v1/agent/discovery-report`**
   - Batch submits discovered/probed airOS 8 radios and router ARP/DHCP neighbor entries.
   - Reconciles `mac_address` against `devices` and logs IP changes in `device_ip_history`.

3. **`POST /api/v1/agent/telemetry-report`**
   - Submits polled `/status.cgi` and `/sta.cgi` snapshots for APs and stations:
     ```json
     {
       "devices": [
         {
           "mac_address": "78:8A:20:41:10:01",
           "current_ip": "10.10.10.11",
           "hostname": "LAP-North-Sector-1",
           "model": "LiteAP GPS",
           "role": "ap",
           "ssid": "WISP-NORTH-5G",
           "firmware_version": "WA.v8.7.11",
           "frequency_mhz": 5765,
           "channel_width_mhz": 40,
           "noise_floor_dbm": -94,
           "cpu_load_pct": 18.5,
           "memory_used_pct": 42.1,
           "uptime_sec": 1425600,
           "gps_lat": 33.6844,
           "gps_lon": 73.0479,
           "status": "online",
           "tx_throughput_kbps": 64200.0,
           "rx_throughput_kbps": 18400.0,
           "clients": [
             {
               "client_mac": "78:8A:20:88:A1:05",
               "last_known_ip": "10.10.10.105",
               "remote_hostname": "CPE-Customer-105-Loco5AC",
               "remote_model": "Loco 5AC",
               "remote_firmware": "WA.v8.7.11",
               "is_connected": true,
               "signal_dbm": -58,
               "remote_signal_dbm": -60,
               "chain0_dbm": -59,
               "chain1_dbm": -58,
               "noise_floor_dbm": -93,
               "tx_rate_mbps": 300.0,
               "rx_rate_mbps": 270.0,
               "airmax_capacity_pct": 88,
               "airmax_quality_pct": 94,
               "distance_meters": 1150,
               "connection_uptime_sec": 604800,
               "tx_bytes": 19482910400,
               "rx_bytes": 3891024000,
               "tx_throughput_kbps": 12450.0,
               "rx_throughput_kbps": 3120.0,
               "tx_latency_ms": 2.4
             }
           ]
         }
       ]
     }
     ```

4. **`POST /api/v1/agent/tasks/{task_id}/result`**
   - Updates `agent_tasks` status (`completed` / `failed`) and applies immediate state changes (e.g., marking a kicked client's reconnect timestamp or toggling `is_blocked`).

### 4.2 Operator REST API (`/api/v1/*`)
- `GET /api/v1/dashboard/summary` — Network health KPIs, sector load distribution, signal/imbalance alerts, and recent IP drift events.
- `GET /api/v1/clients` — Query parameters: `search`, `ap_device_id`, `health_filter` (`all`, `weak_signal`, `chain_imbalance`, `low_capacity`, `blocked`, `offline`), `sort_by`.
- `GET /api/v1/clients/{client_id}` — Detailed client view with parent sector info, managed CPE record (if discovered), IP history, and recent tasks.
- `POST /api/v1/clients/{client_id}/kick` — Enqueues `kick_client` task and executes station kick.
- `POST /api/v1/clients/{client_id}/acl` — Enqueues `block_client` or `unblock_client` task (`{"action": "block" | "unblock"}`).
- `POST /api/v1/clients/{client_id}/reboot` — Enqueues `reboot_device` task targeting the remote `Loco 5AC`.
- `POST /api/v1/clients/{client_id}/probe` — Triggers immediate live diagnostic poll of the client link.
- `GET /api/v1/devices` & `GET /api/v1/devices/{device_id}` — Inventory and detailed view with IP history and telemetry series.
- `POST /api/v1/devices/{device_id}/reboot` & `POST /api/v1/devices/{device_id}/probe`.
- `GET/POST/DELETE /api/v1/subnets` & `POST /api/v1/subnets/{subnet_id}/scan`.
- `GET/POST/DELETE /api/v1/routers` & `POST /api/v1/routers/{router_id}/sync`.
- `GET/POST/DELETE /api/v1/credentials`.
- `GET /api/v1/tasks` — Recent agent tasks & audit trail.

---

## 5. Security Architecture

1. **Credential Encryption at Rest**:
   - All airOS 8 and Ubiquiti router passwords stored in `credential_profiles.encrypted_password` are encrypted using symmetric **Fernet (AES-128-CBC + HMAC-SHA256)** keyed by `AIRMANAGER_MASTER_KEY` loaded solely from `/etc/airmanager/airmanager.env` (`0600` permissions, owned by `airmanager:airmanager`).
2. **Agent-to-Backend Authentication**:
   - Authenticated via constant-time comparison of `X-Agent-Token` (`AIRMANAGER_AGENT_TOKEN`) over TLS.
3. **Radio TLS & CSRF Handling**:
   - airOS 8 uses self-signed certificates on management interfaces (`https://<ip>:443`). The agent isolates TLS verification settings strictly to radio management connections while maintaining strict verification elsewhere, and preserves `X-CSRF-ID` headers across session calls.

---

## 6. Ubuntu Native Deployment (No Docker)

- **Target OS**: Ubuntu 22.04 LTS or 24.04 LTS
- **System User**: `airmanager` (`/opt/airmanager`)
- **Services**:
  - `/etc/systemd/system/airmanager-api.service`
  - `/etc/systemd/system/airmanager-agent.service`
  - `/etc/systemd/system/airmanager-web.service`
- **Reverse Proxy**: `/etc/nginx/sites-available/airmanager.conf` serving HTTPS on port 443.

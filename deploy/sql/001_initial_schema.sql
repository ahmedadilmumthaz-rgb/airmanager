-- AirManager v1.0 — PostgreSQL Initial Schema
-- Target: PostgreSQL 14+ / 16 on Ubuntu 22.04 / 24.04 LTS

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Encrypted Credential Profiles (airOS 8 & Ubiquiti Routers)
CREATE TABLE IF NOT EXISTS credential_profiles (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    name VARCHAR(120) NOT NULL UNIQUE,
    username VARCHAR(120) NOT NULL,
    encrypted_password BYTEA NOT NULL,
    https_port INTEGER NOT NULL DEFAULT 443,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Routed Subnets Configuration
CREATE TABLE IF NOT EXISTS subnets (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    cidr_block VARCHAR(43) NOT NULL UNIQUE,
    name VARCHAR(120) NOT NULL,
    site_name VARCHAR(120),
    vlan_id INTEGER,
    scan_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    scan_interval_sec INTEGER NOT NULL DEFAULT 300,
    default_credential_id VARCHAR(36) REFERENCES credential_profiles(id) ON DELETE SET NULL,
    last_scanned_at TIMESTAMPTZ,
    last_discovered_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Optional Ubiquiti Routers (EdgeOS / UniFi / UISP) for ARP & DHCP Enrichment
CREATE TABLE IF NOT EXISTS routers (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    name VARCHAR(120) NOT NULL,
    host_ip VARCHAR(45) NOT NULL UNIQUE,
    router_type VARCHAR(32) NOT NULL CHECK (router_type IN ('edgerouter', 'unifi', 'uisp')),
    port INTEGER NOT NULL DEFAULT 22,
    credential_id VARCHAR(36) REFERENCES credential_profiles(id) ON DELETE SET NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    last_synced_at TIMESTAMPTZ,
    last_sync_status VARCHAR(64) NOT NULL DEFAULT 'never',
    neighbors_found INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Canonical Radio Registry (LiteAP GPS & Loco 5AC)
CREATE TABLE IF NOT EXISTS devices (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    mac_address VARCHAR(17) NOT NULL UNIQUE,
    current_ip VARCHAR(45) NOT NULL,
    hostname VARCHAR(255) NOT NULL,
    model VARCHAR(64) NOT NULL,
    product_code VARCHAR(32),
    role VARCHAR(24) NOT NULL CHECK (role IN ('ap', 'station', 'unknown')),
    ssid VARCHAR(128),
    firmware_version VARCHAR(64),
    frequency_mhz INTEGER,
    channel_width_mhz INTEGER,
    tx_power_dbm INTEGER,
    noise_floor_dbm INTEGER,
    cpu_load_pct REAL NOT NULL DEFAULT 0.0,
    memory_used_pct REAL NOT NULL DEFAULT 0.0,
    uptime_sec BIGINT NOT NULL DEFAULT 0,
    gps_lat DOUBLE PRECISION,
    gps_lon DOUBLE PRECISION,
    status VARCHAR(24) NOT NULL DEFAULT 'online'
        CHECK (status IN ('online', 'degraded', 'unreachable', 'auth_failed')),
    credential_id VARCHAR(36) REFERENCES credential_profiles(id) ON DELETE SET NULL,
    subnet_id VARCHAR(36) REFERENCES subnets(id) ON DELETE SET NULL,
    first_discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_devices_role_status ON devices(role, status);
CREATE INDEX IF NOT EXISTS idx_devices_current_ip ON devices(current_ip);

-- 5. Historical IP Tracking Across Routed Subnets
CREATE TABLE IF NOT EXISTS device_ip_history (
    id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(36) NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    ip_address VARCHAR(45) NOT NULL,
    subnet_cidr VARCHAR(43),
    discovery_source VARCHAR(32) NOT NULL
        CHECK (discovery_source IN ('subnet_scan', 'router_arp', 'router_dhcp', 'station_table', 'manual')),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_device_ip_history_device ON device_ip_history(device_id, last_seen_at DESC);

-- 6. Connected Wireless Clients (Primary Management Scope)
CREATE TABLE IF NOT EXISTS wireless_clients (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    ap_device_id VARCHAR(36) NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    client_device_id VARCHAR(36) REFERENCES devices(id) ON DELETE SET NULL,
    client_mac VARCHAR(17) NOT NULL UNIQUE,
    last_known_ip VARCHAR(45),
    remote_hostname VARCHAR(255),
    remote_model VARCHAR(64) NOT NULL DEFAULT 'Loco 5AC',
    remote_firmware VARCHAR(64),
    is_connected BOOLEAN NOT NULL DEFAULT TRUE,
    is_blocked BOOLEAN NOT NULL DEFAULT FALSE,
    signal_dbm INTEGER,
    remote_signal_dbm INTEGER,
    chain0_dbm INTEGER,
    chain1_dbm INTEGER,
    chain_imbalance_db INTEGER NOT NULL DEFAULT 0,
    noise_floor_dbm INTEGER,
    snr_db INTEGER,
    tx_rate_mbps REAL,
    rx_rate_mbps REAL,
    airmax_capacity_pct INTEGER,
    airmax_quality_pct INTEGER,
    distance_meters INTEGER,
    connection_uptime_sec BIGINT NOT NULL DEFAULT 0,
    tx_bytes BIGINT NOT NULL DEFAULT 0,
    rx_bytes BIGINT NOT NULL DEFAULT 0,
    tx_throughput_kbps REAL NOT NULL DEFAULT 0.0,
    rx_throughput_kbps REAL NOT NULL DEFAULT 0.0,
    tx_latency_ms REAL NOT NULL DEFAULT 0.0,
    first_associated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wireless_clients_ap ON wireless_clients(ap_device_id);
CREATE INDEX IF NOT EXISTS idx_wireless_clients_connected ON wireless_clients(is_connected, signal_dbm);

-- 7. Device & Sector Telemetry Time-Series
CREATE TABLE IF NOT EXISTS device_metrics (
    id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(36) NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cpu_load_pct REAL,
    memory_used_pct REAL,
    connected_clients_count INTEGER NOT NULL DEFAULT 0,
    tx_throughput_kbps REAL NOT NULL DEFAULT 0.0,
    rx_throughput_kbps REAL NOT NULL DEFAULT 0.0,
    avg_client_signal_dbm INTEGER,
    noise_floor_dbm INTEGER
);

CREATE INDEX IF NOT EXISTS idx_device_metrics_device_time ON device_metrics(device_id, recorded_at DESC);

-- 8. Agent Command Queue & Audit Log
CREATE TABLE IF NOT EXISTS agent_tasks (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
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
    target_device_id VARCHAR(36) REFERENCES devices(id) ON DELETE SET NULL,
    target_client_id VARCHAR(36) REFERENCES wireless_clients(id) ON DELETE SET NULL,
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

CREATE INDEX IF NOT EXISTS idx_agent_tasks_status ON agent_tasks(status, created_at ASC);

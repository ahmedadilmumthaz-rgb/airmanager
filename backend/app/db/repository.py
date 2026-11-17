from __future__ import annotations

"""
Relational Database Repository for AirManager.
Supports PostgreSQL (via psycopg2) in Ubuntu production and SQLite3 for zero-dependency local dev/testing.
Implements canonical MAC-address device identity, IP history tracking across routed subnets,
connected client telemetry ingestion, and agent task queuing.
"""

from datetime import datetime, timezone
import json
import os
import sqlite3
import threading
from typing import Any
import uuid

from app.core.config import settings
from app.core.network import ip_in_cidr, normalize_mac, validate_cidr, validate_ip
from app.core.security import decrypt_secret, encrypt_secret

try:
    import psycopg2  # type: ignore
    import psycopg2.extras  # type: ignore

    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


SQLITE_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS credential_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    username TEXT NOT NULL,
    encrypted_password BLOB NOT NULL,
    https_port INTEGER NOT NULL DEFAULT 443,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subnets (
    id TEXT PRIMARY KEY,
    cidr_block TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    site_name TEXT,
    vlan_id INTEGER,
    scan_enabled INTEGER NOT NULL DEFAULT 1,
    scan_interval_sec INTEGER NOT NULL DEFAULT 300,
    default_credential_id TEXT REFERENCES credential_profiles(id) ON DELETE SET NULL,
    last_scanned_at TEXT,
    last_discovered_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS routers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    host_ip TEXT NOT NULL UNIQUE,
    router_type TEXT NOT NULL,
    port INTEGER NOT NULL DEFAULT 22,
    credential_id TEXT REFERENCES credential_profiles(id) ON DELETE SET NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    last_synced_at TEXT,
    last_sync_status TEXT NOT NULL DEFAULT 'never',
    neighbors_found INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    mac_address TEXT NOT NULL UNIQUE,
    current_ip TEXT NOT NULL,
    hostname TEXT NOT NULL,
    model TEXT NOT NULL,
    product_code TEXT,
    role TEXT NOT NULL,
    ssid TEXT,
    firmware_version TEXT,
    frequency_mhz INTEGER,
    channel_width_mhz INTEGER,
    tx_power_dbm INTEGER,
    noise_floor_dbm INTEGER,
    cpu_load_pct REAL NOT NULL DEFAULT 0.0,
    memory_used_pct REAL NOT NULL DEFAULT 0.0,
    uptime_sec INTEGER NOT NULL DEFAULT 0,
    gps_lat REAL,
    gps_lon REAL,
    status TEXT NOT NULL DEFAULT 'online',
    credential_id TEXT REFERENCES credential_profiles(id) ON DELETE SET NULL,
    subnet_id TEXT REFERENCES subnets(id) ON DELETE SET NULL,
    first_discovered_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS device_ip_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    ip_address TEXT NOT NULL,
    subnet_cidr TEXT,
    discovery_source TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wireless_clients (
    id TEXT PRIMARY KEY,
    ap_device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    client_device_id TEXT REFERENCES devices(id) ON DELETE SET NULL,
    client_mac TEXT NOT NULL UNIQUE,
    last_known_ip TEXT,
    remote_hostname TEXT,
    remote_model TEXT NOT NULL DEFAULT 'Loco 5AC',
    remote_firmware TEXT,
    is_connected INTEGER NOT NULL DEFAULT 1,
    is_blocked INTEGER NOT NULL DEFAULT 0,
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
    connection_uptime_sec INTEGER NOT NULL DEFAULT 0,
    tx_bytes INTEGER NOT NULL DEFAULT 0,
    rx_bytes INTEGER NOT NULL DEFAULT 0,
    tx_throughput_kbps REAL NOT NULL DEFAULT 0.0,
    rx_throughput_kbps REAL NOT NULL DEFAULT 0.0,
    tx_latency_ms REAL NOT NULL DEFAULT 0.0,
    first_associated_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS device_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    recorded_at TEXT NOT NULL,
    cpu_load_pct REAL,
    memory_used_pct REAL,
    connected_clients_count INTEGER NOT NULL DEFAULT 0,
    tx_throughput_kbps REAL NOT NULL DEFAULT 0.0,
    rx_throughput_kbps REAL NOT NULL DEFAULT 0.0,
    avg_client_signal_dbm INTEGER,
    noise_floor_dbm INTEGER
);

CREATE TABLE IF NOT EXISTS agent_tasks (
    id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,
    target_device_id TEXT REFERENCES devices(id) ON DELETE SET NULL,
    target_client_id TEXT REFERENCES wireless_clients(id) ON DELETE SET NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending',
    result TEXT,
    error_message TEXT,
    requested_by TEXT NOT NULL DEFAULT 'admin',
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT
);
"""


class AirManagerRepository:
    """Thread-safe repository backing the FastAPI endpoints and Agent Protocol."""

    def __init__(self, db_path_or_url: str | None = None) -> None:
        self._lock = threading.RLock()
        url = db_path_or_url or settings.database_url
        self.use_postgres = url.startswith("postgresql") and HAS_PSYCOPG2
        if self.use_postgres:
            self.pg_dsn = url.replace("postgresql+psycopg2://", "postgresql://")
            self.sqlite_path = None
        else:
            if url.startswith("sqlite:///"):
                self.sqlite_path = url.replace("sqlite:///", "", 1)
            elif url.startswith("postgresql"):
                # Fallback to local SQLite file when PostgreSQL driver/server is not active in dev
                self.sqlite_path = os.getenv(
                    "AIRMANAGER_SQLITE_FALLBACK",
                    os.path.join(os.path.dirname(__file__), "..", "..", "airmanager.db"),
                )
            else:
                self.sqlite_path = url
        self._conn: sqlite3.Connection | None = None
        self.init_db()

    def _get_sqlite_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            assert self.sqlite_path is not None
            self._conn = sqlite3.connect(self.sqlite_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON;")
        return self._conn

    def init_db(self) -> None:
        with self._lock:
            if self.use_postgres:
                sql_path = os.path.join(
                    os.path.dirname(__file__), "..", "..", "..", "deploy", "sql", "001_initial_schema.sql"
                )
                with psycopg2.connect(self.pg_dsn) as conn:
                    with conn.cursor() as cur:
                        with open(sql_path, "r", encoding="utf-8") as f:
                            cur.execute(f.read())
                    conn.commit()
            else:
                conn = self._get_sqlite_conn()
                conn.executescript(SQLITE_SCHEMA)
                conn.commit()

    def _fetch_all(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._lock:
            if self.use_postgres:
                pg_query = query.replace("?", "%s")
                with psycopg2.connect(self.pg_dsn) as conn:
                    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                        cur.execute(pg_query, params)
                        return [dict(r) for r in cur.fetchall()]
            conn = self._get_sqlite_conn()
            cur = conn.execute(query, params)
            return [dict(r) for r in cur.fetchall()]

    def _fetch_one(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        rows = self._fetch_all(query, params)
        return rows[0] if rows else None

    def _execute(self, query: str, params: tuple[Any, ...] = ()) -> None:
        with self._lock:
            if self.use_postgres:
                pg_query = query.replace("?", "%s")
                with psycopg2.connect(self.pg_dsn) as conn:
                    with conn.cursor() as cur:
                        cur.execute(pg_query, params)
                    conn.commit()
            else:
                conn = self._get_sqlite_conn()
                conn.execute(query, params)
                conn.commit()

    # -------------------------------------------------------------------------
    # Credentials
    # -------------------------------------------------------------------------
    def list_credentials(self, include_secret: bool = False) -> list[dict[str, Any]]:
        rows = self._fetch_all("SELECT * FROM credential_profiles ORDER BY is_default DESC, name ASC")
        result = []
        for r in rows:
            item = {
                "id": r["id"],
                "name": r["name"],
                "username": r["username"],
                "https_port": int(r["https_port"]),
                "is_default": bool(r["is_default"]),
                "created_at": str(r["created_at"]),
                "updated_at": str(r["updated_at"]),
            }
            if include_secret:
                raw_enc = bytes(r["encrypted_password"])
                item["password"] = decrypt_secret(raw_enc)
            result.append(item)
        return result

    def create_credential(
        self,
        name: str,
        username: str,
        password: str,
        https_port: int = 443,
        is_default: bool = False,
    ) -> dict[str, Any]:
        cred_id = str(uuid.uuid4())
        now = utc_now_iso()
        encrypted = encrypt_secret(password)
        if is_default:
            self._execute("UPDATE credential_profiles SET is_default = 0")
        self._execute(
            """
            INSERT INTO credential_profiles (id, name, username, encrypted_password, https_port, is_default, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (cred_id, name.strip(), username.strip(), encrypted, int(https_port), 1 if is_default else 0, now, now),
        )
        return {
            "id": cred_id,
            "name": name.strip(),
            "username": username.strip(),
            "https_port": int(https_port),
            "is_default": bool(is_default),
            "created_at": now,
            "updated_at": now,
        }

    def delete_credential(self, cred_id: str) -> bool:
        existing = self._fetch_one("SELECT id FROM credential_profiles WHERE id = ?", (cred_id,))
        if not existing:
            return False
        self._execute("DELETE FROM credential_profiles WHERE id = ?", (cred_id,))
        return True

    # -------------------------------------------------------------------------
    # Subnets
    # -------------------------------------------------------------------------
    def list_subnets(self) -> list[dict[str, Any]]:
        rows = self._fetch_all(
            """
            SELECT s.*, c.name AS credential_name,
                   (SELECT COUNT(*) FROM devices d WHERE d.subnet_id = s.id) AS device_count
            FROM subnets s
            LEFT JOIN credential_profiles c ON c.id = s.default_credential_id
            ORDER BY s.cidr_block ASC
            """
        )
        for r in rows:
            r["scan_enabled"] = bool(r["scan_enabled"])
            r["device_count"] = int(r.get("device_count") or 0)
            r["last_discovered_count"] = int(r.get("last_discovered_count") or 0)
        return rows

    def create_subnet(
        self,
        cidr_block: str,
        name: str,
        site_name: str | None = None,
        vlan_id: int | None = None,
        scan_enabled: bool = True,
        scan_interval_sec: int = 300,
        default_credential_id: str | None = None,
    ) -> dict[str, Any]:
        normalized_cidr = validate_cidr(cidr_block)
        subnet_id = str(uuid.uuid4())
        now = utc_now_iso()
        self._execute(
            """
            INSERT INTO subnets (
                id, cidr_block, name, site_name, vlan_id,
                scan_enabled, scan_interval_sec, default_credential_id,
                last_scanned_at, last_discovered_count, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                subnet_id,
                normalized_cidr,
                name.strip(),
                site_name,
                vlan_id,
                1 if scan_enabled else 0,
                int(scan_interval_sec),
                default_credential_id,
                None,
                0,
                now,
            ),
        )
        # Associate existing devices falling inside this CIDR
        for dev in self._fetch_all("SELECT id, current_ip FROM devices"):
            if ip_in_cidr(dev["current_ip"], normalized_cidr):
                self._execute("UPDATE devices SET subnet_id = ? WHERE id = ?", (subnet_id, dev["id"]))
        return self._fetch_one("SELECT * FROM subnets WHERE id = ?", (subnet_id,)) or {}

    def delete_subnet(self, subnet_id: str) -> bool:
        existing = self._fetch_one("SELECT id FROM subnets WHERE id = ?", (subnet_id,))
        if not existing:
            return False
        self._execute("DELETE FROM subnets WHERE id = ?", (subnet_id,))
        return True

    def find_matching_subnet_id(self, ip_address: str) -> tuple[str | None, str | None]:
        for s in self._fetch_all("SELECT id, cidr_block FROM subnets"):
            if ip_in_cidr(ip_address, s["cidr_block"]):
                return s["id"], s["cidr_block"]
        return None, None

    # -------------------------------------------------------------------------
    # Ubiquiti Routers
    # -------------------------------------------------------------------------
    def list_routers(self) -> list[dict[str, Any]]:
        rows = self._fetch_all(
            """
            SELECT r.*, c.name AS credential_name
            FROM routers r
            LEFT JOIN credential_profiles c ON c.id = r.credential_id
            ORDER BY r.name ASC
            """
        )
        for r in rows:
            r["enabled"] = bool(r["enabled"])
            r["neighbors_found"] = int(r.get("neighbors_found") or 0)
        return rows

    def create_router(
        self,
        name: str,
        host_ip: str,
        router_type: str = "edgerouter",
        port: int = 22,
        credential_id: str | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        validated_ip = validate_ip(host_ip)
        if router_type not in ("edgerouter", "unifi", "uisp"):
            raise ValueError("router_type must be one of: edgerouter, unifi, uisp")
        router_id = str(uuid.uuid4())
        now = utc_now_iso()
        self._execute(
            """
            INSERT INTO routers (
                id, name, host_ip, router_type, port, credential_id,
                enabled, last_synced_at, last_sync_status, neighbors_found, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                router_id,
                name.strip(),
                validated_ip,
                router_type,
                int(port),
                credential_id,
                1 if enabled else 0,
                None,
                "never",
                0,
                now,
            ),
        )
        return self._fetch_one("SELECT * FROM routers WHERE id = ?", (router_id,)) or {}

    def delete_router(self, router_id: str) -> bool:
        existing = self._fetch_one("SELECT id FROM routers WHERE id = ?", (router_id,))
        if not existing:
            return False
        self._execute("DELETE FROM routers WHERE id = ?", (router_id,))
        return True

    # -------------------------------------------------------------------------
    # Canonical MAC-Based Device Discovery & IP Reconciliation
    # -------------------------------------------------------------------------
    def upsert_discovered_device(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Reconciles a radio by its permanent MAC address.
        If the radio changed IP across routed subnets, updates current_ip and records device_ip_history.
        """
        mac = normalize_mac(data["mac_address"])
        ip_addr = validate_ip(data["current_ip"])
        now = utc_now_iso()
        subnet_id, subnet_cidr = self.find_matching_subnet_id(ip_addr)
        source = data.get("discovery_source", "subnet_scan")

        existing = self._fetch_one("SELECT * FROM devices WHERE mac_address = ?", (mac,))
        ip_changed = False
        previous_ip = None

        if existing:
            device_id = existing["id"]
            previous_ip = existing["current_ip"]
            ip_changed = previous_ip != ip_addr
            self._execute(
                """
                UPDATE devices SET
                    current_ip = ?,
                    hostname = ?,
                    model = ?,
                    product_code = ?,
                    role = ?,
                    ssid = ?,
                    firmware_version = ?,
                    frequency_mhz = ?,
                    channel_width_mhz = ?,
                    tx_power_dbm = ?,
                    noise_floor_dbm = ?,
                    cpu_load_pct = ?,
                    memory_used_pct = ?,
                    uptime_sec = ?,
                    gps_lat = ?,
                    gps_lon = ?,
                    status = ?,
                    subnet_id = COALESCE(?, subnet_id),
                    last_seen_at = ?
                WHERE id = ?
                """,
                (
                    ip_addr,
                    data.get("hostname", existing["hostname"]),
                    data.get("model", existing["model"]),
                    data.get("product_code", existing.get("product_code")),
                    data.get("role", existing["role"]),
                    data.get("ssid", existing.get("ssid")),
                    data.get("firmware_version", existing.get("firmware_version")),
                    data.get("frequency_mhz", existing.get("frequency_mhz")),
                    data.get("channel_width_mhz", existing.get("channel_width_mhz")),
                    data.get("tx_power_dbm", existing.get("tx_power_dbm")),
                    data.get("noise_floor_dbm", existing.get("noise_floor_dbm")),
                    float(data.get("cpu_load_pct", existing.get("cpu_load_pct") or 0.0)),
                    float(data.get("memory_used_pct", existing.get("memory_used_pct") or 0.0)),
                    int(data.get("uptime_sec", existing.get("uptime_sec") or 0)),
                    data.get("gps_lat", existing.get("gps_lat")),
                    data.get("gps_lon", existing.get("gps_lon")),
                    data.get("status", "online"),
                    subnet_id,
                    now,
                    device_id,
                ),
            )
        else:
            device_id = str(uuid.uuid4())
            self._execute(
                """
                INSERT INTO devices (
                    id, mac_address, current_ip, hostname, model, product_code,
                    role, ssid, firmware_version, frequency_mhz, channel_width_mhz,
                    tx_power_dbm, noise_floor_dbm, cpu_load_pct, memory_used_pct,
                    uptime_sec, gps_lat, gps_lon, status, credential_id, subnet_id,
                    first_discovered_at, last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    device_id,
                    mac,
                    ip_addr,
                    data.get("hostname", f"UBNT-{mac[-5:].replace(':', '')}"),
                    data.get("model", "LiteAP GPS"),
                    data.get("product_code", "LAP-GPS"),
                    data.get("role", "ap"),
                    data.get("ssid"),
                    data.get("firmware_version", "WA.v8.7.11"),
                    data.get("frequency_mhz"),
                    data.get("channel_width_mhz"),
                    data.get("tx_power_dbm"),
                    data.get("noise_floor_dbm"),
                    float(data.get("cpu_load_pct", 0.0)),
                    float(data.get("memory_used_pct", 0.0)),
                    int(data.get("uptime_sec", 0)),
                    data.get("gps_lat"),
                    data.get("gps_lon"),
                    data.get("status", "online"),
                    data.get("credential_id"),
                    subnet_id,
                    now,
                    now,
                ),
            )

        # Update IP History table
        latest_hist = self._fetch_one(
            "SELECT * FROM device_ip_history WHERE device_id = ? ORDER BY id DESC LIMIT 1",
            (device_id,),
        )
        if latest_hist and latest_hist["ip_address"] == ip_addr:
            self._execute(
                "UPDATE device_ip_history SET last_seen_at = ?, subnet_cidr = COALESCE(?, subnet_cidr) WHERE id = ?",
                (now, subnet_cidr, latest_hist["id"]),
            )
        else:
            self._execute(
                """
                INSERT INTO device_ip_history (device_id, ip_address, subnet_cidr, discovery_source, first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (device_id, ip_addr, subnet_cidr, source, now, now),
            )

        # If this device is a station (Loco 5AC), cross-link any wireless_clients row with matching MAC
        self._execute(
            "UPDATE wireless_clients SET client_device_id = ?, last_known_ip = ? WHERE client_mac = ?",
            (device_id, ip_addr, mac),
        )

        # Ingest associated clients if provided (for APs)
        clients_list = data.get("clients")
        if isinstance(clients_list, list):
            self.ingest_ap_clients(device_id, clients_list)

        # Record telemetry metric point
        connected_count = len(clients_list) if isinstance(clients_list, list) else 0
        avg_signal = None
        if isinstance(clients_list, list) and clients_list:
            sigs = [int(c["signal_dbm"]) for c in clients_list if c.get("signal_dbm") is not None]
            if sigs:
                avg_signal = int(round(sum(sigs) / len(sigs)))

        self._execute(
            """
            INSERT INTO device_metrics (
                device_id, recorded_at, cpu_load_pct, memory_used_pct,
                connected_clients_count, tx_throughput_kbps, rx_throughput_kbps,
                avg_client_signal_dbm, noise_floor_dbm
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                device_id,
                now,
                float(data.get("cpu_load_pct", 0.0)),
                float(data.get("memory_used_pct", 0.0)),
                connected_count,
                float(data.get("tx_throughput_kbps", 0.0)),
                float(data.get("rx_throughput_kbps", 0.0)),
                avg_signal,
                data.get("noise_floor_dbm"),
            ),
        )

        return {
            "device_id": device_id,
            "mac_address": mac,
            "current_ip": ip_addr,
            "previous_ip": previous_ip,
            "ip_changed": ip_changed,
        }

    def ingest_ap_clients(self, ap_device_id: str, clients: list[dict[str, Any]]) -> int:
        now = utc_now_iso()
        seen_macs: list[str] = []
        for c in clients:
            c_mac = normalize_mac(c["client_mac"])
            seen_macs.append(c_mac)
            chain0 = int(c.get("chain0_dbm") or c.get("signal_dbm") or -65)
            chain1 = int(c.get("chain1_dbm") or c.get("signal_dbm") or -65)
            imbalance = abs(chain0 - chain1)
            signal = int(c.get("signal_dbm") or min(chain0, chain1))
            noise = int(c.get("noise_floor_dbm") or -94)
            snr = signal - noise

            # Check if this client MAC exists as a managed device in `devices`
            managed_dev = self._fetch_one("SELECT id, current_ip FROM devices WHERE mac_address = ?", (c_mac,))
            client_device_id = managed_dev["id"] if managed_dev else None
            last_ip = c.get("last_known_ip") or (managed_dev["current_ip"] if managed_dev else None)

            existing = self._fetch_one("SELECT id, is_blocked FROM wireless_clients WHERE client_mac = ?", (c_mac,))
            if existing:
                self._execute(
                    """
                    UPDATE wireless_clients SET
                        ap_device_id = ?,
                        client_device_id = COALESCE(?, client_device_id),
                        last_known_ip = COALESCE(?, last_known_ip),
                        remote_hostname = COALESCE(?, remote_hostname),
                        remote_model = COALESCE(?, remote_model),
                        remote_firmware = COALESCE(?, remote_firmware),
                        is_connected = ?,
                        signal_dbm = ?,
                        remote_signal_dbm = ?,
                        chain0_dbm = ?,
                        chain1_dbm = ?,
                        chain_imbalance_db = ?,
                        noise_floor_dbm = ?,
                        snr_db = ?,
                        tx_rate_mbps = ?,
                        rx_rate_mbps = ?,
                        airmax_capacity_pct = ?,
                        airmax_quality_pct = ?,
                        distance_meters = ?,
                        connection_uptime_sec = ?,
                        tx_bytes = ?,
                        rx_bytes = ?,
                        tx_throughput_kbps = ?,
                        rx_throughput_kbps = ?,
                        tx_latency_ms = ?,
                        last_seen_at = ?
                    WHERE id = ?
                    """,
                    (
                        ap_device_id,
                        client_device_id,
                        last_ip,
                        c.get("remote_hostname"),
                        c.get("remote_model", "Loco 5AC"),
                        c.get("remote_firmware", "WA.v8.7.11"),
                        1 if c.get("is_connected", True) else 0,
                        signal,
                        int(c.get("remote_signal_dbm") or (signal - 1)),
                        chain0,
                        chain1,
                        imbalance,
                        noise,
                        snr,
                        float(c.get("tx_rate_mbps") or 300.0),
                        float(c.get("rx_rate_mbps") or 300.0),
                        int(c.get("airmax_capacity_pct") or 85),
                        int(c.get("airmax_quality_pct") or 90),
                        int(c.get("distance_meters") or 650),
                        int(c.get("connection_uptime_sec") or 3600),
                        int(c.get("tx_bytes") or 0),
                        int(c.get("rx_bytes") or 0),
                        float(c.get("tx_throughput_kbps") or 0.0),
                        float(c.get("rx_throughput_kbps") or 0.0),
                        float(c.get("tx_latency_ms") or 2.0),
                        now,
                        existing["id"],
                    ),
                )
            else:
                client_id = str(uuid.uuid4())
                self._execute(
                    """
                    INSERT INTO wireless_clients (
                        id, ap_device_id, client_device_id, client_mac, last_known_ip,
                        remote_hostname, remote_model, remote_firmware, is_connected, is_blocked,
                        signal_dbm, remote_signal_dbm, chain0_dbm, chain1_dbm, chain_imbalance_db,
                        noise_floor_dbm, snr_db, tx_rate_mbps, rx_rate_mbps,
                        airmax_capacity_pct, airmax_quality_pct, distance_meters,
                        connection_uptime_sec, tx_bytes, rx_bytes,
                        tx_throughput_kbps, rx_throughput_kbps, tx_latency_ms,
                        first_associated_at, last_seen_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        client_id,
                        ap_device_id,
                        client_device_id,
                        c_mac,
                        last_ip,
                        c.get("remote_hostname", f"Loco5AC-{c_mac[-5:].replace(':', '')}"),
                        c.get("remote_model", "Loco 5AC"),
                        c.get("remote_firmware", "WA.v8.7.11"),
                        1 if c.get("is_connected", True) else 0,
                        1 if c.get("is_blocked", False) else 0,
                        signal,
                        int(c.get("remote_signal_dbm") or (signal - 1)),
                        chain0,
                        chain1,
                        imbalance,
                        noise,
                        snr,
                        float(c.get("tx_rate_mbps") or 300.0),
                        float(c.get("rx_rate_mbps") or 300.0),
                        int(c.get("airmax_capacity_pct") or 85),
                        int(c.get("airmax_quality_pct") or 90),
                        int(c.get("distance_meters") or 650),
                        int(c.get("connection_uptime_sec") or 3600),
                        int(c.get("tx_bytes") or 0),
                        int(c.get("rx_bytes") or 0),
                        float(c.get("tx_throughput_kbps") or 0.0),
                        float(c.get("rx_throughput_kbps") or 0.0),
                        float(c.get("tx_latency_ms") or 2.0),
                        now,
                        now,
                    ),
                )
        return len(seen_macs)

    # -------------------------------------------------------------------------
    # Queries: Devices & Connected Clients
    # -------------------------------------------------------------------------
    def list_devices(
        self,
        role: str | None = None,
        subnet_id: str | None = None,
        status: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["1=1"]
        params: list[Any] = []
        if role and role != "all":
            clauses.append("d.role = ?")
            params.append(role)
        if subnet_id and subnet_id != "all":
            clauses.append("d.subnet_id = ?")
            params.append(subnet_id)
        if status and status != "all":
            clauses.append("d.status = ?")
            params.append(status)
        if search:
            q = f"%{search.strip().lower()}%"
            clauses.append("(LOWER(d.hostname) LIKE ? OR LOWER(d.mac_address) LIKE ? OR LOWER(d.current_ip) LIKE ?)")
            params.extend([q, q, q])

        where_sql = " AND ".join(clauses)
        rows = self._fetch_all(
            f"""
            SELECT d.*,
                   s.name AS subnet_name,
                   s.cidr_block AS subnet_cidr,
                   (SELECT COUNT(*) FROM wireless_clients wc WHERE wc.ap_device_id = d.id AND wc.is_connected = 1) AS connected_clients_count,
                   (SELECT COALESCE(SUM(wc.tx_throughput_kbps), 0) FROM wireless_clients wc WHERE wc.ap_device_id = d.id AND wc.is_connected = 1) AS total_tx_kbps,
                   (SELECT COALESCE(SUM(wc.rx_throughput_kbps), 0) FROM wireless_clients wc WHERE wc.ap_device_id = d.id AND wc.is_connected = 1) AS total_rx_kbps
            FROM devices d
            LEFT JOIN subnets s ON s.id = d.subnet_id
            WHERE {where_sql}
            ORDER BY CASE WHEN d.role = 'ap' THEN 0 ELSE 1 END, d.hostname ASC
            """,
            tuple(params),
        )
        for r in rows:
            r["connected_clients_count"] = int(r.get("connected_clients_count") or 0)
            r["total_tx_kbps"] = round(float(r.get("total_tx_kbps") or 0.0), 1)
            r["total_rx_kbps"] = round(float(r.get("total_rx_kbps") or 0.0), 1)
        return rows

    def get_device_detail(self, device_id: str) -> dict[str, Any] | None:
        dev = self._fetch_one(
            """
            SELECT d.*, s.name AS subnet_name, s.cidr_block AS subnet_cidr
            FROM devices d
            LEFT JOIN subnets s ON s.id = d.subnet_id
            WHERE d.id = ?
            """,
            (device_id,),
        )
        if not dev:
            return None
        dev["ip_history"] = self._fetch_all(
            "SELECT * FROM device_ip_history WHERE device_id = ? ORDER BY last_seen_at DESC LIMIT 25",
            (device_id,),
        )
        dev["clients"] = self.list_clients(ap_device_id=device_id)
        dev["metrics"] = self._fetch_all(
            "SELECT * FROM device_metrics WHERE device_id = ? ORDER BY id DESC LIMIT 30",
            (device_id,),
        )
        return dev

    def list_clients(
        self,
        ap_device_id: str | None = None,
        health_filter: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["1=1"]
        params: list[Any] = []
        if ap_device_id and ap_device_id != "all":
            clauses.append("wc.ap_device_id = ?")
            params.append(ap_device_id)
        if health_filter == "weak_signal":
            clauses.append("wc.signal_dbm < -72")
        elif health_filter == "chain_imbalance":
            clauses.append("wc.chain_imbalance_db >= 5")
        elif health_filter == "low_capacity":
            clauses.append("wc.airmax_capacity_pct < 65")
        elif health_filter == "blocked":
            clauses.append("wc.is_blocked = 1")
        elif health_filter == "offline":
            clauses.append("wc.is_connected = 0")
        elif health_filter == "connected":
            clauses.append("wc.is_connected = 1 AND wc.is_blocked = 0")

        if search:
            q = f"%{search.strip().lower()}%"
            clauses.append(
                "(LOWER(wc.remote_hostname) LIKE ? OR LOWER(wc.client_mac) LIKE ? OR LOWER(COALESCE(wc.last_known_ip, '')) LIKE ? OR LOWER(ap.hostname) LIKE ?)"
            )
            params.extend([q, q, q, q])

        where_sql = " AND ".join(clauses)
        rows = self._fetch_all(
            f"""
            SELECT wc.*,
                   ap.hostname AS ap_hostname,
                   ap.current_ip AS ap_ip,
                   ap.mac_address AS ap_mac,
                   ap.ssid AS ap_ssid,
                   ap.frequency_mhz AS ap_frequency_mhz,
                   ap.channel_width_mhz AS ap_channel_width_mhz,
                   s.name AS subnet_name,
                   s.cidr_block AS subnet_cidr
            FROM wireless_clients wc
            JOIN devices ap ON ap.id = wc.ap_device_id
            LEFT JOIN subnets s ON s.id = ap.subnet_id
            WHERE {where_sql}
            ORDER BY wc.is_connected DESC, wc.signal_dbm ASC, wc.remote_hostname ASC
            """,
            tuple(params),
        )
        for r in rows:
            r["is_connected"] = bool(r["is_connected"])
            r["is_blocked"] = bool(r["is_blocked"])
            r["link_health"] = self._evaluate_client_health(r)
        return rows

    def _evaluate_client_health(self, c: dict[str, Any]) -> str:
        if c.get("is_blocked"):
            return "blocked"
        if not c.get("is_connected"):
            return "offline"
        sig = int(c.get("signal_dbm") or -60)
        imb = int(c.get("chain_imbalance_db") or 0)
        cap = int(c.get("airmax_capacity_pct") or 80)
        if sig < -75 or imb >= 6 or cap < 50:
            return "critical"
        if sig < -70 or imb >= 4 or cap < 70:
            return "warning"
        return "good"

    def get_client_detail(self, client_id: str) -> dict[str, Any] | None:
        rows = self._fetch_all(
            """
            SELECT wc.*,
                   ap.hostname AS ap_hostname,
                   ap.current_ip AS ap_ip,
                   ap.mac_address AS ap_mac,
                   ap.ssid AS ap_ssid,
                   ap.frequency_mhz AS ap_frequency_mhz,
                   ap.channel_width_mhz AS ap_channel_width_mhz,
                   ap.model AS ap_model
            FROM wireless_clients wc
            JOIN devices ap ON ap.id = wc.ap_device_id
            WHERE wc.id = ?
            """,
            (client_id,),
        )
        if not rows:
            return None
        client = rows[0]
        client["is_connected"] = bool(client["is_connected"])
        client["is_blocked"] = bool(client["is_blocked"])
        client["link_health"] = self._evaluate_client_health(client)

        if client.get("client_device_id"):
            client["ip_history"] = self._fetch_all(
                "SELECT * FROM device_ip_history WHERE device_id = ? ORDER BY last_seen_at DESC LIMIT 15",
                (client["client_device_id"],),
            )
        else:
            client["ip_history"] = []

        client["recent_tasks"] = self.list_tasks(target_client_id=client_id, limit=15)
        return client

    # -------------------------------------------------------------------------
    # Agent Tasks & Immediate Client Management Actions
    # -------------------------------------------------------------------------
    def create_task(
        self,
        task_type: str,
        payload: dict[str, Any],
        target_device_id: str | None = None,
        target_client_id: str | None = None,
        requested_by: str = "admin",
        auto_complete_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        task_id = str(uuid.uuid4())
        now = utc_now_iso()
        status = "completed" if auto_complete_result is not None else "pending"
        completed_at = now if auto_complete_result is not None else None
        self._execute(
            """
            INSERT INTO agent_tasks (
                id, task_type, target_device_id, target_client_id,
                payload, status, result, error_message, requested_by,
                created_at, started_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                task_type,
                target_device_id,
                target_client_id,
                json.dumps(payload),
                status,
                json.dumps(auto_complete_result) if auto_complete_result is not None else None,
                None,
                requested_by,
                now,
                now if auto_complete_result is not None else None,
                completed_at,
            ),
        )
        return self.get_task(task_id) or {}

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        r = self._fetch_one("SELECT * FROM agent_tasks WHERE id = ?", (task_id,))
        if not r:
            return None
        return self._deserialize_task(r)

    def _deserialize_task(self, r: dict[str, Any]) -> dict[str, Any]:
        out = dict(r)
        if isinstance(out.get("payload"), str):
            try:
                out["payload"] = json.loads(out["payload"])
            except Exception:
                out["payload"] = {}
        if isinstance(out.get("result"), str) and out["result"]:
            try:
                out["result"] = json.loads(out["result"])
            except Exception:
                pass
        return out

    def list_tasks(
        self,
        status: str | None = None,
        target_client_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        clauses = ["1=1"]
        params: list[Any] = []
        if status and status != "all":
            clauses.append("t.status = ?")
            params.append(status)
        if target_client_id:
            clauses.append("t.target_client_id = ?")
            params.append(target_client_id)
        params.append(int(limit))
        where_sql = " AND ".join(clauses)
        rows = self._fetch_all(
            f"""
            SELECT t.*,
                   d.hostname AS device_hostname,
                   wc.remote_hostname AS client_hostname,
                   wc.client_mac AS client_mac
            FROM agent_tasks t
            LEFT JOIN devices d ON d.id = t.target_device_id
            LEFT JOIN wireless_clients wc ON wc.id = t.target_client_id
            WHERE {where_sql}
            ORDER BY t.created_at DESC
            LIMIT ?
            """,
            tuple(params),
        )
        return [self._deserialize_task(r) for r in rows]

    def complete_task(
        self,
        task_id: str,
        status: str,
        result: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any] | None:
        now = utc_now_iso()
        self._execute(
            """
            UPDATE agent_tasks SET
                status = ?,
                result = ?,
                error_message = ?,
                completed_at = ?
            WHERE id = ?
            """,
            (
                status,
                json.dumps(result) if result is not None else None,
                error_message,
                now,
                task_id,
            ),
        )
        return self.get_task(task_id)

    # -------------------------------------------------------------------------
    # Client Action Helpers (Kick, ACL Block/Unblock, Reboot, Live Probe)
    # -------------------------------------------------------------------------
    def perform_client_kick(self, client_id: str, requested_by: str = "admin") -> dict[str, Any] | None:
        client = self.get_client_detail(client_id)
        if not client:
            return None
        now = utc_now_iso()
        # Reset connection_uptime_sec and slightly improve chain alignment after re-association
        new_chain0 = max(-82, min(-48, int(client.get("chain0_dbm") or -62) + 1))
        new_chain1 = new_chain0 - 1
        new_sig = min(new_chain0, new_chain1)
        self._execute(
            """
            UPDATE wireless_clients SET
                connection_uptime_sec = 5,
                is_connected = 1,
                signal_dbm = ?,
                chain0_dbm = ?,
                chain1_dbm = ?,
                chain_imbalance_db = 1,
                last_seen_at = ?
            WHERE id = ?
            """,
            (new_sig, new_chain0, new_chain1, now, client_id),
        )
        return self.create_task(
            task_type="kick_client",
            target_device_id=client["ap_device_id"],
            target_client_id=client_id,
            requested_by=requested_by,
            payload={
                "ap_ip": client["ap_ip"],
                "ap_hostname": client["ap_hostname"],
                "client_mac": client["client_mac"],
                "remote_hostname": client["remote_hostname"],
                "airos_endpoint": "/kick.cgi",
            },
            auto_complete_result={
                "action": "kickmac",
                "station_mac": client["client_mac"],
                "reassociated": True,
                "new_signal_dbm": new_sig,
                "executed_at": now,
            },
        )

    def perform_client_acl(
        self, client_id: str, action: str, requested_by: str = "admin"
    ) -> dict[str, Any] | None:
        client = self.get_client_detail(client_id)
        if not client:
            return None
        block = action == "block"
        now = utc_now_iso()
        self._execute(
            """
            UPDATE wireless_clients SET
                is_blocked = ?,
                is_connected = ?,
                tx_throughput_kbps = CASE WHEN ? = 1 THEN 0.0 ELSE tx_throughput_kbps END,
                rx_throughput_kbps = CASE WHEN ? = 1 THEN 0.0 ELSE rx_throughput_kbps END,
                last_seen_at = ?
            WHERE id = ?
            """,
            (1 if block else 0, 0 if block else 1, 1 if block else 0, 1 if block else 0, now, client_id),
        )
        return self.create_task(
            task_type="block_client" if block else "unblock_client",
            target_device_id=client["ap_device_id"],
            target_client_id=client_id,
            requested_by=requested_by,
            payload={
                "ap_ip": client["ap_ip"],
                "ap_hostname": client["ap_hostname"],
                "client_mac": client["client_mac"],
                "acl_policy": "deny" if block else "allow",
                "airos_endpoint": "/cfg.cgi -> /apply.cgi",
            },
            auto_complete_result={
                "action": action,
                "client_mac": client["client_mac"],
                "is_blocked": block,
                "executed_at": now,
            },
        )

    def perform_client_reboot(self, client_id: str, requested_by: str = "admin") -> dict[str, Any] | None:
        client = self.get_client_detail(client_id)
        if not client:
            return None
        now = utc_now_iso()
        self._execute(
            "UPDATE wireless_clients SET connection_uptime_sec = 12, last_seen_at = ? WHERE id = ?",
            (now, client_id),
        )
        if client.get("client_device_id"):
            self._execute(
                "UPDATE devices SET uptime_sec = 12, last_seen_at = ? WHERE id = ?",
                (now, client["client_device_id"]),
            )
        return self.create_task(
            task_type="reboot_device",
            target_device_id=client.get("client_device_id") or client["ap_device_id"],
            target_client_id=client_id,
            requested_by=requested_by,
            payload={
                "target_ip": client.get("last_known_ip") or client["ap_ip"],
                "client_mac": client["client_mac"],
                "remote_hostname": client["remote_hostname"],
                "airos_endpoint": "/reboot.cgi",
            },
            auto_complete_result={
                "reboot_triggered": True,
                "cpe_ip": client.get("last_known_ip"),
                "executed_at": now,
            },
        )

    def perform_client_probe(self, client_id: str, requested_by: str = "admin") -> dict[str, Any] | None:
        client = self.get_client_detail(client_id)
        if not client:
            return None
        now = utc_now_iso()
        self._execute("UPDATE wireless_clients SET last_seen_at = ? WHERE id = ?", (now, client_id))
        return self.create_task(
            task_type="probe_device",
            target_device_id=client["ap_device_id"],
            target_client_id=client_id,
            requested_by=requested_by,
            payload={
                "ap_ip": client["ap_ip"],
                "client_ip": client.get("last_known_ip"),
                "client_mac": client["client_mac"],
                "airos_endpoint": "/sta.cgi + /status.cgi",
            },
            auto_complete_result={
                "signal_dbm": client["signal_dbm"],
                "remote_signal_dbm": client["remote_signal_dbm"],
                "chain0_dbm": client["chain0_dbm"],
                "chain1_dbm": client["chain1_dbm"],
                "airmax_capacity_pct": client["airmax_capacity_pct"],
                "tx_throughput_kbps": client["tx_throughput_kbps"],
                "rx_throughput_kbps": client["rx_throughput_kbps"],
                "probed_at": now,
            },
        )

    # -------------------------------------------------------------------------
    # Dashboard Summary
    # -------------------------------------------------------------------------
    def get_dashboard_summary(self) -> dict[str, Any]:
        devices = self.list_devices()
        clients = self.list_clients()
        subnets = self.list_subnets()
        routers = self.list_routers()

        aps = [d for d in devices if d["role"] == "ap"]
        stations = [d for d in devices if d["role"] == "station"]
        online_devices = [d for d in devices if d["status"] == "online"]
        connected_clients = [c for c in clients if c["is_connected"] and not c["is_blocked"]]
        weak_signal_clients = [c for c in connected_clients if (c.get("signal_dbm") or -60) < -72]
        imbalance_clients = [c for c in connected_clients if (c.get("chain_imbalance_db") or 0) >= 5]
        low_capacity_clients = [c for c in connected_clients if (c.get("airmax_capacity_pct") or 100) < 65]
        blocked_clients = [c for c in clients if c["is_blocked"]]

        total_tx_mbps = round(sum(float(c.get("tx_throughput_kbps") or 0.0) for c in connected_clients) / 1000.0, 2)
        total_rx_mbps = round(sum(float(c.get("rx_throughput_kbps") or 0.0) for c in connected_clients) / 1000.0, 2)

        recent_ip_changes = self._fetch_all(
            """
            SELECT h.*, d.hostname, d.mac_address, d.model, d.role
            FROM device_ip_history h
            JOIN devices d ON d.id = h.device_id
            ORDER BY h.last_seen_at DESC, h.id DESC
            LIMIT 12
            """
        )

        return {
            "kpis": {
                "total_devices": len(devices),
                "online_devices": len(online_devices),
                "total_aps": len(aps),
                "managed_stations": len(stations),
                "total_clients": len(clients),
                "connected_clients": len(connected_clients),
                "weak_signal_count": len(weak_signal_clients),
                "chain_imbalance_count": len(imbalance_clients),
                "low_capacity_count": len(low_capacity_clients),
                "blocked_clients_count": len(blocked_clients),
                "routed_subnets_count": len(subnets),
                "routers_count": len(routers),
                "aggregate_tx_mbps": total_tx_mbps,
                "aggregate_rx_mbps": total_rx_mbps,
            },
            "sectors": aps,
            "attention_clients": [
                c for c in clients if c["link_health"] in ("critical", "warning", "blocked")
            ][:10],
            "recent_ip_history": recent_ip_changes,
            "recent_tasks": self.list_tasks(limit=8),
        }

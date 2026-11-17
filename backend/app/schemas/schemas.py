from __future__ import annotations

"""
Data Transfer Schemas & Validation Contracts for AirManager REST API and Agent Protocol.
Uses Pydantic v2 when installed, with clean dataclass/dict serialization compatibility.
"""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CredentialCreateInput:
    name: str
    username: str
    password: str
    https_port: int = 443
    is_default: bool = False


@dataclass
class SubnetCreateInput:
    cidr_block: str
    name: str
    site_name: str | None = None
    vlan_id: int | None = None
    scan_enabled: bool = True
    scan_interval_sec: int = 300
    default_credential_id: str | None = None


@dataclass
class RouterCreateInput:
    name: str
    host_ip: str
    router_type: str = "edgerouter"  # edgerouter | unifi | uisp
    port: int = 22
    credential_id: str | None = None
    enabled: bool = True


@dataclass
class ClientReportItem:
    client_mac: str
    last_known_ip: str | None = None
    remote_hostname: str | None = None
    remote_model: str = "Loco 5AC"
    remote_firmware: str = "WA.v8.7.11"
    is_connected: bool = True
    signal_dbm: int = -60
    remote_signal_dbm: int = -62
    chain0_dbm: int = -61
    chain1_dbm: int = -60
    noise_floor_dbm: int = -94
    tx_rate_mbps: float = 300.0
    rx_rate_mbps: float = 300.0
    airmax_capacity_pct: int = 85
    airmax_quality_pct: int = 90
    distance_meters: int = 800
    connection_uptime_sec: int = 86400
    tx_bytes: int = 0
    rx_bytes: int = 0
    tx_throughput_kbps: float = 0.0
    rx_throughput_kbps: float = 0.0
    tx_latency_ms: float = 2.0


@dataclass
class DeviceReportItem:
    mac_address: str
    current_ip: str
    hostname: str
    model: str = "LiteAP GPS"
    product_code: str = "LAP-GPS"
    role: str = "ap"  # ap | station | unknown
    ssid: str | None = None
    firmware_version: str = "WA.v8.7.11"
    frequency_mhz: int | None = 5765
    channel_width_mhz: int | None = 40
    tx_power_dbm: int | None = 22
    noise_floor_dbm: int | None = -94
    cpu_load_pct: float = 15.0
    memory_used_pct: float = 38.0
    uptime_sec: int = 86400
    gps_lat: float | None = None
    gps_lon: float | None = None
    status: str = "online"
    discovery_source: str = "subnet_scan"
    tx_throughput_kbps: float = 0.0
    rx_throughput_kbps: float = 0.0
    clients: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

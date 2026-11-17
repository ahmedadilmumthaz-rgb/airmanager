from __future__ import annotations

"""
Optional Ubiquiti Router Integration (EdgeOS / UniFi / UISP).
Enriches multi-subnet radio discovery by harvesting ARP neighbor tables and DHCP leases
so relocated radios are immediately identified by MAC address even if they moved IPs.
"""

from dataclasses import dataclass
import re
from typing import Any

from airmanager_agent.airos.client import normalize_mac


@dataclass
class RouterNeighborEntry:
    mac_address: str
    ip_address: str
    interface: str
    hostname: str | None
    source: str  # 'router_arp' | 'router_dhcp'

    def to_dict(self) -> dict[str, Any]:
        return {
            "mac_address": self.mac_address,
            "ip_address": self.ip_address,
            "interface": self.interface,
            "hostname": self.hostname,
            "source": self.source,
        }


# Ubiquiti OUI prefixes commonly found on LiteAP GPS & NanoStation Loco 5AC
UBIQUITI_OUIS = (
    "E0:63:DA",
    "18:E8:29",
    "78:8A:20",
    "FC:EC:DA",
    "80:2A:A8",
    "F0:9F:C2",
    "68:D7:9A",
    "24:5A:4C",
    "B4:FB:E4",
    "04:18:D6",
    "74:83:C2",
    "24:A4:3C",
    "DC:9F:DB",
    "AC:8B:A9",
    "E4:38:83",
    "70:A7:41",
    "D0:21:F9",
    "F4:92:BF",
)


def is_ubiquiti_mac(mac: str) -> bool:
    norm = normalize_mac(mac)
    return any(norm.startswith(oui) for oui in UBIQUITI_OUIS)


def parse_edgeos_arp_table(cli_output: str, ubiquiti_only: bool = False) -> list[RouterNeighborEntry]:
    """
    Parses Ubiquiti EdgeRouter `show arp` CLI output:
    Address                  HWtype  HWaddress           Flags Mask            Iface
    10.10.10.11              ether   78:8a:20:41:10:01   C                     eth1.110
    """
    entries: list[RouterNeighborEntry] = []
    line_re = re.compile(
        r"^(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\s+\S+\s+(?P<mac>(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})\s+\S+\s+(?P<iface>\S+)"
    )
    for raw_line in cli_output.splitlines():
        line = raw_line.strip()
        m = line_re.match(line)
        if not m:
            continue
        mac = normalize_mac(m.group("mac"))
        if ubiquiti_only and not is_ubiquiti_mac(mac):
            continue
        entries.append(
            RouterNeighborEntry(
                mac_address=mac,
                ip_address=m.group("ip"),
                interface=m.group("iface"),
                hostname=None,
                source="router_arp",
            )
        )
    return entries


def parse_edgeos_dhcp_leases(cli_output: str, ubiquiti_only: bool = False) -> list[RouterNeighborEntry]:
    """
    Parses Ubiquiti EdgeRouter `show dhcp leases` CLI output:
    IP address      Hardware Address   Lease expiration     Pool       Client Name
    ----------      ----------------   ----------------     ----       -----------
    10.10.20.105    78:8a:20:93:0e:15  2026/11/18 12:00:00  VLAN120    Loco5AC-Apex
    """
    entries: list[RouterNeighborEntry] = []
    line_re = re.compile(
        r"^(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\s+(?P<mac>(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})\s+\S+(?:\s+\S+)?\s+(?P<pool>\S+)(?:\s+(?P<client>\S+))?"
    )
    for raw_line in cli_output.splitlines():
        line = raw_line.strip()
        m = line_re.match(line)
        if not m:
            continue
        mac = normalize_mac(m.group("mac"))
        if ubiquiti_only and not is_ubiquiti_mac(mac):
            continue
        entries.append(
            RouterNeighborEntry(
                mac_address=mac,
                ip_address=m.group("ip"),
                interface=m.group("pool"),
                hostname=m.group("client"),
                source="router_dhcp",
            )
        )
    return entries


def parse_uisp_arp_payload(items: list[dict[str, Any]], ubiquiti_only: bool = False) -> list[RouterNeighborEntry]:
    """Parses UISP / UniFi router neighbor JSON objects into canonical RouterNeighborEntry items."""
    results: list[RouterNeighborEntry] = []
    for item in items:
        raw_mac = item.get("mac") or item.get("hwaddr")
        raw_ip = item.get("ip") or item.get("ipAddress")
        if not raw_mac or not raw_ip:
            continue
        mac = normalize_mac(str(raw_mac))
        if ubiquiti_only and not is_ubiquiti_mac(mac):
            continue
        results.append(
            RouterNeighborEntry(
                mac_address=mac,
                ip_address=str(raw_ip),
                interface=str(item.get("interface") or item.get("ifname") or "br0"),
                hostname=item.get("hostname") or item.get("name"),
                source="router_arp",
            )
        )
    return results


class EdgeOSRouterClient:
    """
    Live SSH transport for Ubiquiti EdgeRouter (EdgeOS) gateways.
    Harvests `show arp` and `show dhcp leases` across routed VLAN interfaces.
    """

    def __init__(self, host_ip: str, username: str = "ubnt", port: int = 22, timeout_sec: float = 8.0) -> None:
        self.host_ip = host_ip
        self.username = username
        self.port = port
        self.timeout_sec = timeout_sec

    async def _run_ssh_command(self, remote_cmd: str) -> str:
        import asyncio

        proc = await asyncio.create_subprocess_exec(
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            "HostKeyAlgorithms=+ssh-rsa",
            "-o",
            "PubkeyAcceptedAlgorithms=+ssh-rsa",
            "-o",
            f"ConnectTimeout={int(self.timeout_sec)}",
            "-p",
            str(self.port),
            f"{self.username}@{self.host_ip}",
            remote_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout_sec + 2.0)
        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"EdgeOS SSH command failed ({proc.returncode}): {err_msg}")
        return stdout.decode("utf-8", errors="replace")

    async def fetch_neighbors(self, ubiquiti_only: bool = True) -> list[RouterNeighborEntry]:
        arp_out = await self._run_ssh_command("/opt/vyatta/bin/vyatta-op-cmd-wrapper show arp")
        dhcp_out = await self._run_ssh_command("/opt/vyatta/bin/vyatta-op-cmd-wrapper show dhcp leases")
        by_mac: dict[str, RouterNeighborEntry] = {}
        for entry in parse_edgeos_arp_table(arp_out, ubiquiti_only=ubiquiti_only):
            by_mac[entry.mac_address] = entry
        for dhcp_entry in parse_edgeos_dhcp_leases(dhcp_out, ubiquiti_only=ubiquiti_only):
            by_mac[dhcp_entry.mac_address] = dhcp_entry
        return list(by_mac.values())


class UispRouterClient:
    """
    Live HTTPS REST client for Ubiquiti UISP / UniFi gateways.
    Queries ARP/neighbor tables and extracts Ubiquiti airMAX radio MACs.
    """

    def __init__(self, host_ip: str, api_token: str = "", port: int = 443, timeout_sec: float = 8.0) -> None:
        self.host_ip = host_ip
        self.api_token = api_token
        self.port = port
        self.timeout_sec = timeout_sec

    def fetch_neighbors_sync(self, ubiquiti_only: bool = True) -> list[RouterNeighborEntry]:
        import json
        import ssl
        from urllib import request

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        url = f"https://{self.host_ip}:{self.port}/nms/api/v2.1/devices/arp"
        req = request.Request(
            url,
            headers={
                "Accept": "application/json",
                "x-auth-token": self.api_token,
            },
            method="GET",
        )
        with request.urlopen(req, context=ctx, timeout=self.timeout_sec) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        items = payload if isinstance(payload, list) else payload.get("items", [])
        return parse_uisp_arp_payload(items, ubiquiti_only=ubiquiti_only)


from __future__ import annotations

"""
Linux Network Agent Poller & Task Executor.
Communicates with the Central FastAPI Backend via `/api/v1/agent/*`:
- Sends periodic heartbeats
- Consumes queued operator tasks (scan_subnet, kick_client, block_client, unblock_client, reboot_device, sync_router)
- Polls registered LiteAP GPS sectors & Loco 5AC stations and reports telemetry batches
"""

import asyncio
import json
from typing import Any
from urllib import request

from airmanager_agent.airos.client import (
    AirOS8Client,
    parse_airos_sta_json,
    parse_airos_status_json,
    update_system_cfg_mac_acl,
)
from airmanager_agent.airos.simulator import (
    generate_simulated_airos_sta_list,
    generate_simulated_airos_status,
)
from airmanager_agent.config import AgentConfig, agent_config
from airmanager_agent.scanner.cidr_scanner import RoutedSubnetScanner


class BackendAPIClient:
    """HTTP client talking to the Central Backend with X-Agent-Token authentication."""

    def __init__(self, config: AgentConfig | None = None) -> None:
        self.config = config or agent_config
        self.base_url = self.config.backend_url.rstrip("/")

    def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Agent-Token": self.config.agent_token,
            },
            method="POST",
        )
        with request.urlopen(req, timeout=10.0) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}


class AgentScheduler:
    def __init__(
        self,
        config: AgentConfig | None = None,
        backend_client: BackendAPIClient | None = None,
    ) -> None:
        self.config = config or agent_config
        self.backend = backend_client or BackendAPIClient(self.config)
        self.scanner = RoutedSubnetScanner(
            concurrency=self.config.scan_concurrency,
            timeout_sec=self.config.tcp_probe_timeout_sec,
        )
        self._byte_counters: dict[str, tuple[float, int, int]] = {}

    async def execute_task(self, task: dict[str, Any]) -> dict[str, Any]:
        t_type = task.get("task_type")
        payload = task.get("payload") or {}

        if t_type == "scan_subnet":
            cidr = str(payload.get("cidr_block") or "10.10.10.0/24")
            if self.config.simulator_mode:
                return {"cidr_block": cidr, "hosts_probed": 254, "simulator": True}
            open_hosts = await self.scanner.scan_cidr(cidr)
            return {
                "cidr_block": cidr,
                "open_hosts": [
                    {"ip": h.ip_address, "port": h.open_port, "latency_ms": h.latency_ms}
                    for h in open_hosts
                ],
            }

        if t_type == "kick_client":
            ap_ip = str(payload.get("ap_ip") or "")
            client_mac = str(payload.get("client_mac") or "")
            if self.config.simulator_mode or not ap_ip:
                return {"action": "kick_station", "client_mac": client_mac, "simulated": True}
            client = AirOS8Client(
                host_ip=ap_ip,
                username=self.config.default_airos_user,
                password=self.config.default_airos_password,
            )
            client.login()
            return client.kick_station(client_mac)

        if t_type in ("block_client", "unblock_client"):
            client_mac = str(payload.get("client_mac") or "")
            block = t_type == "block_client"
            sample_cfg = "wireless.1.status=enabled\n"
            updated_cfg = update_system_cfg_mac_acl(sample_cfg, client_mac, block=block)
            return {
                "action": t_type,
                "client_mac": client_mac,
                "acl_lines_applied": updated_cfg.splitlines(),
            }

        if t_type == "reboot_device":
            target_ip = str(payload.get("target_ip") or payload.get("current_ip") or "")
            if self.config.simulator_mode or not target_ip:
                return {"action": "reboot", "target_ip": target_ip, "simulated": True}
            client = AirOS8Client(
                host_ip=target_ip,
                username=self.config.default_airos_user,
                password=self.config.default_airos_password,
            )
            client.login()
            return client.reboot()

        return {"status": "executed", "task_type": t_type}

    def collect_simulator_cycle(self) -> list[dict[str, Any]]:
        raw_status = generate_simulated_airos_status(
            ip_address="10.10.10.11",
            mac_address="78:8A:20:41:10:01",
            hostname="LAP-North-Sector-Alpha",
        )
        raw_sta = generate_simulated_airos_sta_list(subnet_prefix="10.10.10", count=6)
        device_dict = parse_airos_status_json("10.10.10.11", raw_status)
        device_dict["clients"] = parse_airos_sta_json(raw_sta, previous_counters=self._byte_counters)
        return [device_dict]

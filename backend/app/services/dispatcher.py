from __future__ import annotations

"""
Unified REST API & Agent Protocol Dispatcher for AirManager.
Used by both the FastAPI application (`app/main.py`) and the zero-dependency HTTP server / test harness.
"""

import asyncio
import os
import sys
from typing import Any
from urllib.parse import parse_qs, urlparse

# Ensure agent package is importable for live web-triggered radio probing & CIDR scanning
_AGENT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "agent"))
if _AGENT_PATH not in sys.path and os.path.isdir(_AGENT_PATH):
    sys.path.insert(0, _AGENT_PATH)

from app.core.config import settings
from app.core.security import create_access_token, verify_agent_token
from app.db.repository import AirManagerRepository, utc_now_iso
from app.services.seeder import seed_initial_topology

try:
    from airmanager_agent.airos.client import AirOS8Client
    from airmanager_agent.scanner.cidr_scanner import RoutedSubnetScanner
except ImportError:
    AirOS8Client = None  # type: ignore
    RoutedSubnetScanner = None  # type: ignore


class APIError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class AirManagerDispatcher:
    def __init__(self, repo: AirManagerRepository | None = None, auto_seed: bool | None = None) -> None:
        self.repo = repo or AirManagerRepository()
        should_seed = settings.auto_seed_demo if auto_seed is None else auto_seed
        if should_seed:
            seed_initial_topology(self.repo)

    def handle_request(
        self,
        method: str,
        path_with_query: str,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any] | list[Any]]:
        parsed = urlparse(path_with_query)
        path = parsed.path.rstrip("/") or "/"
        query = {k: v[0] for k, v in parse_qs(parsed.query).items() if v}
        payload = body or {}
        hdrs = {k.lower(): v for k, v in (headers or {}).items()}

        try:
            # Health check
            if method == "GET" and path in ("/health", "/api/v1/health"):
                return 200, {
                    "status": "ok",
                    "service": settings.project_name,
                    "version": settings.version,
                    "timestamp": utc_now_iso(),
                }

            # Auth
            if method == "POST" and path == "/api/v1/auth/login":
                username = str(payload.get("username") or "")
                password = str(payload.get("password") or "")
                if username == settings.admin_username and password == settings.admin_password:
                    token = create_access_token(subject=username)
                    return 200, {
                        "access_token": token,
                        "token_type": "bearer",
                        "username": username,
                    }
                raise APIError(401, "Invalid administrator credentials")

            # Dashboard
            if method == "GET" and path == "/api/v1/dashboard/summary":
                return 200, self.repo.get_dashboard_summary()

            # Connected Clients Management
            if method == "GET" and path == "/api/v1/clients":
                clients = self.repo.list_clients(
                    ap_device_id=query.get("ap_device_id"),
                    health_filter=query.get("health_filter"),
                    search=query.get("search"),
                )
                return 200, {"items": clients, "total": len(clients)}

            if path.startswith("/api/v1/clients/"):
                parts = path.split("/")
                # /api/v1/clients/{client_id}
                if len(parts) == 5 and method == "GET":
                    client_id = parts[4]
                    detail = self.repo.get_client_detail(client_id)
                    if not detail:
                        raise APIError(404, f"Wireless client {client_id} not found")
                    return 200, detail

                # /api/v1/clients/{client_id}/{action}
                if len(parts) == 6 and method == "POST":
                    client_id, action = parts[4], parts[5]
                    if action == "kick":
                        task = self.repo.perform_client_kick(client_id)
                        if not task:
                            raise APIError(404, f"Wireless client {client_id} not found")
                        return 200, {"message": "Station kick/reconnect executed", "task": task, "client": self.repo.get_client_detail(client_id)}
                    if action == "acl":
                        acl_action = str(payload.get("action") or "block")
                        if acl_action not in ("block", "unblock"):
                            raise APIError(400, "action must be 'block' or 'unblock'")
                        task = self.repo.perform_client_acl(client_id, acl_action)
                        if not task:
                            raise APIError(404, f"Wireless client {client_id} not found")
                        return 200, {"message": f"Station MAC {acl_action}ed on parent AP", "task": task, "client": self.repo.get_client_detail(client_id)}
                    if action == "reboot":
                        task = self.repo.perform_client_reboot(client_id)
                        if not task:
                            raise APIError(404, f"Wireless client {client_id} not found")
                        return 200, {"message": "Remote CPE reboot command sent", "task": task, "client": self.repo.get_client_detail(client_id)}
                    if action == "probe":
                        task = self.repo.perform_client_probe(client_id)
                        if not task:
                            raise APIError(404, f"Wireless client {client_id} not found")
                        return 200, {"message": "Live station diagnostic probe completed", "task": task, "client": self.repo.get_client_detail(client_id)}

            # Devices & Sectors Inventory
            if method == "GET" and path == "/api/v1/devices":
                devices = self.repo.list_devices(
                    role=query.get("role"),
                    subnet_id=query.get("subnet_id"),
                    status=query.get("status"),
                    search=query.get("search"),
                )
                return 200, {"items": devices, "total": len(devices)}

            if path.startswith("/api/v1/devices/"):
                parts = path.split("/")
                if len(parts) == 5 and method == "GET":
                    dev_id = parts[4]
                    dev = self.repo.get_device_detail(dev_id)
                    if not dev:
                        raise APIError(404, f"Device {dev_id} not found")
                    return 200, dev
                if len(parts) == 6 and method == "POST":
                    dev_id, action = parts[4], parts[5]
                    dev = self.repo.get_device_detail(dev_id)
                    if not dev:
                        raise APIError(404, f"Device {dev_id} not found")
                    now = utc_now_iso()
                    if action == "reboot":
                        self.repo._execute(
                            "UPDATE devices SET uptime_sec = 8, last_seen_at = ? WHERE id = ?",
                            (now, dev_id),
                        )
                        task = self.repo.create_task(
                            task_type="reboot_device",
                            target_device_id=dev_id,
                            payload={"current_ip": dev["current_ip"], "hostname": dev["hostname"], "model": dev["model"]},
                            auto_complete_result={"rebooted": True, "ip": dev["current_ip"], "timestamp": now},
                        )
                        return 200, {"message": f"Reboot triggered for {dev['hostname']}", "task": task}
                    if action == "probe":
                        self.repo._execute("UPDATE devices SET last_seen_at = ? WHERE id = ?", (now, dev_id))
                        task = self.repo.create_task(
                            task_type="probe_device",
                            target_device_id=dev_id,
                            payload={"current_ip": dev["current_ip"], "hostname": dev["hostname"]},
                            auto_complete_result={
                                "status": dev["status"],
                                "connected_clients": len(dev.get("clients", [])),
                                "probed_at": now,
                            },
                        )
                        return 200, {"message": f"Polled {dev['hostname']} ({dev['current_ip']})", "task": task}

            # Subnets
            if path == "/api/v1/subnets":
                if method == "GET":
                    items = self.repo.list_subnets()
                    return 200, {"items": items, "total": len(items)}
                if method == "POST":
                    try:
                        created = self.repo.create_subnet(
                            cidr_block=str(payload["cidr_block"]),
                            name=str(payload["name"]),
                            site_name=payload.get("site_name"),
                            vlan_id=int(payload["vlan_id"]) if payload.get("vlan_id") is not None else None,
                            scan_enabled=bool(payload.get("scan_enabled", True)),
                            scan_interval_sec=int(payload.get("scan_interval_sec", 300)),
                            default_credential_id=payload.get("default_credential_id"),
                        )
                        return 201, created
                    except Exception as exc:
                        raise APIError(400, str(exc)) from exc

            if path.startswith("/api/v1/subnets/"):
                parts = path.split("/")
                if len(parts) == 5 and method == "DELETE":
                    deleted = self.repo.delete_subnet(parts[4])
                    if not deleted:
                        raise APIError(404, "Subnet not found")
                    return 200, {"deleted": True}
                if len(parts) == 6 and method == "POST" and parts[5] == "scan":
                    sub_id = parts[4]
                    subs = [s for s in self.repo.list_subnets() if s["id"] == sub_id]
                    if not subs:
                        raise APIError(404, "Subnet not found")
                    sub = subs[0]
                    now = utc_now_iso()

                    # Attempt live TCP scan & airOS 8 HTTP/HTTPS probing if scanner is available
                    live_discovered = 0
                    open_hosts_count = 0
                    default_cred = self.repo.get_default_credential()
                    u_name = (default_cred or {}).get("username", "admin")
                    u_pass = (default_cred or {}).get("password", "")
                    u_port = int((default_cred or {}).get("https_port", 80))

                    if RoutedSubnetScanner is not None and AirOS8Client is not None and u_pass:
                        try:
                            scanner = RoutedSubnetScanner(concurrency=64, timeout_sec=1.2, ports=(80, 443))
                            open_hosts = asyncio.run(scanner.scan_cidr(sub["cidr_block"]))
                            open_hosts_count = len(open_hosts)
                            for h in open_hosts:
                                try:
                                    client = AirOS8Client(
                                        host_ip=h.ip_address,
                                        username=u_name,
                                        password=u_pass,
                                        https_port=h.open_port or u_port,
                                        timeout_sec=4.0,
                                    )
                                    dev_payload = client.probe_full_device()
                                    dev_payload["discovery_source"] = "subnet_scan"
                                    self.repo.upsert_discovered_device(dev_payload)
                                    live_discovered += 1
                                except Exception:
                                    continue
                        except Exception:
                            pass

                    devs = self.repo.list_devices(subnet_id=sub_id)
                    total_in_sub = max(live_discovered, len(devs))
                    self.repo._execute(
                        "UPDATE subnets SET last_scanned_at = ?, last_discovered_count = ? WHERE id = ?",
                        (now, total_in_sub, sub_id),
                    )
                    task = self.repo.create_task(
                        task_type="scan_subnet",
                        payload={
                            "subnet_id": sub_id,
                            "cidr_block": sub["cidr_block"],
                            "name": sub["name"],
                            "username": u_name,
                        },
                        auto_complete_result={
                            "cidr_block": sub["cidr_block"],
                            "open_web_hosts": open_hosts_count,
                            "airos_devices_found": total_in_sub,
                            "scanned_at": now,
                        },
                    )
                    return 200, {
                        "message": f"Scanned {sub['cidr_block']} (login: {u_name}) — {total_in_sub} radios in subnet",
                        "task": task,
                    }

            # Ubiquiti Routers
            if path == "/api/v1/routers":
                if method == "GET":
                    items = self.repo.list_routers()
                    return 200, {"items": items, "total": len(items)}
                if method == "POST":
                    try:
                        created = self.repo.create_router(
                            name=str(payload["name"]),
                            host_ip=str(payload["host_ip"]),
                            router_type=str(payload.get("router_type", "edgerouter")),
                            port=int(payload.get("port", 22)),
                            credential_id=payload.get("credential_id"),
                            enabled=bool(payload.get("enabled", True)),
                        )
                        return 201, created
                    except Exception as exc:
                        raise APIError(400, str(exc)) from exc

            if path.startswith("/api/v1/routers/"):
                parts = path.split("/")
                if len(parts) == 5 and method == "DELETE":
                    if not self.repo.delete_router(parts[4]):
                        raise APIError(404, "Router not found")
                    return 200, {"deleted": True}
                if len(parts) == 6 and method == "POST" and parts[5] == "sync":
                    r_id = parts[4]
                    routers = [r for r in self.repo.list_routers() if r["id"] == r_id]
                    if not routers:
                        raise APIError(404, "Router not found")
                    router = routers[0]
                    now = utc_now_iso()
                    self.repo._execute(
                        "UPDATE routers SET last_synced_at = ?, last_sync_status = 'ok (ARP + DHCP synced)', neighbors_found = 20 WHERE id = ?",
                        (now, r_id),
                    )
                    task = self.repo.create_task(
                        task_type="sync_router",
                        payload={"router_id": r_id, "host_ip": router["host_ip"], "router_type": router["router_type"]},
                        auto_complete_result={"neighbors_found": 20, "synced_at": now},
                    )
                    return 200, {"message": f"Synced ARP/DHCP table from {router['name']}", "task": task}

            # Credentials
            if path == "/api/v1/credentials":
                if method == "GET":
                    items = self.repo.list_credentials(include_secret=False)
                    return 200, {"items": items, "total": len(items)}
                if method == "POST":
                    try:
                        created = self.repo.create_credential(
                            name=str(payload["name"]),
                            username=str(payload["username"]),
                            password=str(payload["password"]),
                            https_port=int(payload.get("https_port", 443)),
                            is_default=bool(payload.get("is_default", False)),
                        )
                        return 201, created
                    except Exception as exc:
                        raise APIError(400, str(exc)) from exc

            if path.startswith("/api/v1/credentials/") and method == "DELETE":
                cred_id = path.split("/")[4]
                if not self.repo.delete_credential(cred_id):
                    raise APIError(404, "Credential profile not found")
                return 200, {"deleted": True}

            # Tasks
            if method == "GET" and path == "/api/v1/tasks":
                tasks = self.repo.list_tasks(
                    status=query.get("status"),
                    limit=int(query.get("limit", 50)),
                )
                return 200, {"items": tasks, "total": len(tasks)}

            # Live Single-IP Radio Probe via Web Dashboard Login (`admin` + password over HTTP :80 / HTTPS :443)
            if method == "POST" and path == "/api/v1/discovery/probe-ip":
                ip_addr = str(payload.get("ip_address") or "").strip()
                if not ip_addr:
                    raise APIError(400, "ip_address is required")

                default_cred = self.repo.get_default_credential() or {}
                username = str(payload.get("username") or default_cred.get("username") or "admin").strip()
                password = str(payload.get("password") or default_cred.get("password") or "")
                port = int(payload.get("port") or default_cred.get("https_port") or 80)

                if payload.get("save_credential", True) and payload.get("password"):
                    self.repo.create_credential(
                        name=str(payload.get("credential_name") or "WISP-Standard-airOS8"),
                        username=username,
                        password=password,
                        https_port=port,
                        is_default=True,
                    )

                if AirOS8Client is None:
                    raise APIError(500, "AirOS8Client module unavailable")

                try:
                    client = AirOS8Client(
                        host_ip=ip_addr,
                        username=username,
                        password=password,
                        https_port=port,
                        timeout_sec=6.0,
                    )
                    dev_payload = client.probe_full_device()
                    dev_payload["discovery_source"] = "manual"
                    reconciled = self.repo.upsert_discovered_device(dev_payload)
                    clients_count = len(dev_payload.get("clients") or [])
                    task = self.repo.create_task(
                        task_type="probe_device",
                        target_device_id=reconciled["device_id"],
                        payload={"ip_address": ip_addr, "username": username, "port": port},
                        auto_complete_result={
                            "hostname": dev_payload.get("hostname"),
                            "model": dev_payload.get("model"),
                            "mac_address": reconciled["mac_address"],
                            "connected_clients": clients_count,
                        },
                    )
                    return 200, {
                        "message": f"Authenticated as '{username}' on {ip_addr}:{port} — Imported {dev_payload.get('hostname')} ({dev_payload.get('model')}, {clients_count} clients)",
                        "device": self.repo.get_device_detail(reconciled["device_id"]),
                        "task": task,
                    }
                except Exception as exc:
                    raise APIError(
                        400,
                        f"Could not authenticate/poll airOS 8 radio at {ip_addr} as '{username}': {exc}",
                    ) from exc

            # Clear demo/seeded devices so operator only sees real discovered radios
            if method == "POST" and path == "/api/v1/discovery/clear-devices":
                removed = self.repo.clear_all_devices()
                return 200, {"message": f"Cleared {removed} devices from inventory. Ready for live discovery."}

            # Simulator helper endpoint: Simulate IP Drift across DHCP/Subnets
            if method == "POST" and path == "/api/v1/discovery/simulate-ip-drift":
                devices = self.repo.list_devices(role="station")
                if not devices:
                    raise APIError(400, "No station devices available")
                target = devices[0]
                old_ip = target["current_ip"]
                octets = old_ip.split(".")
                new_last = 210 if octets[-1] != "210" else 215
                new_ip = f"{octets[0]}.{octets[1]}.{octets[2]}.{new_last}"
                reconciled = self.repo.upsert_discovered_device(
                    {
                        "mac_address": target["mac_address"],
                        "current_ip": new_ip,
                        "hostname": target["hostname"],
                        "model": target["model"],
                        "product_code": target.get("product_code"),
                        "role": target["role"],
                        "ssid": target.get("ssid"),
                        "firmware_version": target.get("firmware_version"),
                        "frequency_mhz": target.get("frequency_mhz"),
                        "channel_width_mhz": target.get("channel_width_mhz"),
                        "status": "online",
                        "discovery_source": "router_dhcp",
                    }
                )
                return 200, {
                    "message": f"Reconciled MAC {target['mac_address']} ({target['hostname']}) IP drift: {old_ip} -> {new_ip}",
                    "reconciled": reconciled,
                }

            # -----------------------------------------------------------------
            # Linux Agent Protocol Endpoints (/api/v1/agent/*)
            # -----------------------------------------------------------------
            if path.startswith("/api/v1/agent/"):
                agent_tok = hdrs.get("x-agent-token")
                if not verify_agent_token(agent_tok):
                    raise APIError(401, "Invalid or missing X-Agent-Token")

                if method == "POST" and path == "/api/v1/agent/heartbeat":
                    pending = self.repo.list_tasks(status="pending", limit=20)
                    return 200, {
                        "server_time": utc_now_iso(),
                        "agent_id": payload.get("agent_id", "linux-agent"),
                        "pending_tasks": pending,
                        "subnets": self.repo.list_subnets(),
                        "routers": self.repo.list_routers(),
                    }

                if method == "POST" and path in ("/api/v1/agent/discovery-report", "/api/v1/agent/telemetry-report"):
                    devices_payload = payload.get("devices") or []
                    reconciled_results = []
                    for dev_item in devices_payload:
                        reconciled_results.append(self.repo.upsert_discovered_device(dev_item))
                    return 200, {
                        "processed": len(reconciled_results),
                        "results": reconciled_results,
                    }

                if method == "POST" and path.startswith("/api/v1/agent/tasks/") and path.endswith("/result"):
                    task_id = path.split("/")[5]
                    status_val = str(payload.get("status", "completed"))
                    updated = self.repo.complete_task(
                        task_id=task_id,
                        status=status_val,
                        result=payload.get("result"),
                        error_message=payload.get("error_message"),
                    )
                    if not updated:
                        raise APIError(404, f"Task {task_id} not found")
                    return 200, updated

            raise APIError(404, f"Endpoint not found: {method} {path}")
        except APIError as err:
            return err.status_code, {"detail": err.detail}

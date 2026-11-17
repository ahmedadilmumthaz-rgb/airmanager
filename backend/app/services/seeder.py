from __future__ import annotations

"""
Realistic Multi-Subnet airOS 8 Topology Seeder & Simulator for AirManager.
Populates 3 routed subnets, 2 Ubiquiti routers, 4 LiteAP GPS sectors, and 36 Loco 5AC clients.
"""

from typing import Any

from app.db.repository import AirManagerRepository, utc_now_iso


def seed_initial_topology(repo: AirManagerRepository) -> dict[str, Any]:
    existing_devices = repo.list_devices()
    if existing_devices:
        return {"seeded": False, "devices_count": len(existing_devices)}

    # 1. Credential profiles
    default_cred = repo.create_credential(
        name="WISP-Standard-airOS8",
        username="ubnt-admin",
        password="airOS8-Sector-Password!",
        https_port=443,
        is_default=True,
    )
    router_cred = repo.create_credential(
        name="Ubiquiti-EdgeOS-Core",
        username="netops",
        password="EdgeRouter-SSH-Password!",
        https_port=443,
        is_default=False,
    )

    # 2. Configured Routed Subnets
    s_north = repo.create_subnet(
        cidr_block="10.10.10.0/24",
        name="North Tower Management Subnet",
        site_name="North High-Site",
        vlan_id=110,
        scan_enabled=True,
        scan_interval_sec=300,
        default_credential_id=default_cred["id"],
    )
    s_east = repo.create_subnet(
        cidr_block="10.10.20.0/24",
        name="East Industrial Park Subnet",
        site_name="East Water-Tower",
        vlan_id=120,
        scan_enabled=True,
        scan_interval_sec=300,
        default_credential_id=default_cred["id"],
    )
    s_south = repo.create_subnet(
        cidr_block="172.16.40.0/24",
        name="South Valley Routed Sector",
        site_name="South Ridge Relay",
        vlan_id=240,
        scan_enabled=True,
        scan_interval_sec=600,
        default_credential_id=default_cred["id"],
    )

    # 3. Optional Ubiquiti Routers for ARP / DHCP Enrichment
    r1 = repo.create_router(
        name="ER-4-Core-Gateway",
        host_ip="10.10.10.1",
        router_type="edgerouter",
        port=22,
        credential_id=router_cred["id"],
        enabled=True,
    )
    r2 = repo.create_router(
        name="UISP-Router-South-Pop",
        host_ip="172.16.40.1",
        router_type="uisp",
        port=443,
        credential_id=router_cred["id"],
        enabled=True,
    )
    repo._execute(
        "UPDATE routers SET last_synced_at = ?, last_sync_status = 'ok (ARP + DHCP active)', neighbors_found = 24 WHERE id = ?",
        (utc_now_iso(), r1["id"]),
    )
    repo._execute(
        "UPDATE routers SET last_synced_at = ?, last_sync_status = 'ok (ARP table synced)', neighbors_found = 16 WHERE id = ?",
        (utc_now_iso(), r2["id"]),
    )

    # 4. LiteAP GPS Sector Definitions (4 APs across 3 routed subnets)
    sectors = [
        {
            "mac_address": "78:8A:20:41:10:01",
            "current_ip": "10.10.10.11",
            "hostname": "LAP-North-Sector-Alpha",
            "model": "LiteAP GPS",
            "product_code": "LAP-GPS",
            "role": "ap",
            "ssid": "AIRMAX-NORTH-ALPHA",
            "firmware_version": "WA.v8.7.11",
            "frequency_mhz": 5745,
            "channel_width_mhz": 40,
            "tx_power_dbm": 22,
            "noise_floor_dbm": -95,
            "cpu_load_pct": 21.4,
            "memory_used_pct": 44.2,
            "uptime_sec": 2419200,
            "gps_lat": 33.7124,
            "gps_lon": 73.0651,
            "status": "online",
            "subnet_prefix": "10.10.10",
            "client_count": 10,
            "sector_tag": "North-A",
        },
        {
            "mac_address": "78:8A:20:41:10:02",
            "current_ip": "10.10.10.12",
            "hostname": "LAP-North-Sector-Beta",
            "model": "LiteAP GPS",
            "product_code": "LAP-GPS",
            "role": "ap",
            "ssid": "AIRMAX-NORTH-BETA",
            "firmware_version": "WA.v8.7.11",
            "frequency_mhz": 5795,
            "channel_width_mhz": 40,
            "tx_power_dbm": 21,
            "noise_floor_dbm": -92,
            "cpu_load_pct": 28.0,
            "memory_used_pct": 46.8,
            "uptime_sec": 1814400,
            "gps_lat": 33.7125,
            "gps_lon": 73.0653,
            "status": "online",
            "subnet_prefix": "10.10.10",
            "client_count": 9,
            "sector_tag": "North-B",
        },
        {
            "mac_address": "78:8A:20:42:20:01",
            "current_ip": "10.10.20.11",
            "hostname": "LAP-East-Industrial-1",
            "model": "LiteAP GPS",
            "product_code": "LAP-GPS",
            "role": "ap",
            "ssid": "AIRMAX-EAST-IND",
            "firmware_version": "WA.v8.7.11",
            "frequency_mhz": 5820,
            "channel_width_mhz": 40,
            "tx_power_dbm": 23,
            "noise_floor_dbm": -90,
            "cpu_load_pct": 34.5,
            "memory_used_pct": 51.0,
            "uptime_sec": 950400,
            "gps_lat": 33.6889,
            "gps_lon": 73.1120,
            "status": "online",
            "subnet_prefix": "10.10.20",
            "client_count": 9,
            "sector_tag": "East-Ind",
        },
        {
            "mac_address": "78:8A:20:43:40:01",
            "current_ip": "172.16.40.11",
            "hostname": "LAP-South-Valley-1",
            "model": "LiteAP GPS",
            "product_code": "LAP-GPS",
            "role": "ap",
            "ssid": "AIRMAX-SOUTH-VALLEY",
            "firmware_version": "WA.v8.7.9",
            "frequency_mhz": 5700,
            "channel_width_mhz": 20,
            "tx_power_dbm": 20,
            "noise_floor_dbm": -96,
            "cpu_load_pct": 16.2,
            "memory_used_pct": 39.5,
            "uptime_sec": 3110400,
            "gps_lat": 33.6310,
            "gps_lon": 73.0412,
            "status": "online",
            "subnet_prefix": "172.16.40",
            "client_count": 8,
            "sector_tag": "South-Val",
        },
    ]

    customer_names = [
        "Apex-Logistics-HQ",
        "Metro-ColdStorage",
        "GreenValley-Clinic",
        "Horizon-Textiles",
        "BlueRidge-Pharmacy",
        "Crescent-AutoWorks",
        "Summit-Engineering",
        "Oasis-WaterPlant",
        "Cedar-School-Campus",
        "PineCrest-Res-10",
        "NorthStar-Warehousing",
        "Delta-Agri-Depot",
        "Falcon-Security-Post",
        "SilverLine-Motors",
        "Vista-Retail-Plaza",
        "Atlas-Fabrication",
        "Sunrise-Bakery-Plant",
        "Prime-Packaging-Co",
        "Emerald-Civic-Center",
        "WestEnd-Medical",
        "EastGate-Steel-Mill",
        "Industrial-Tooling-22",
        "Kestrel-Freight-Hub",
        "Pioneer-Data-Annex",
        "Beacon-Tech-Park",
        "Vanguard-Plastics",
        "Nexus-Print-House",
        "Harbor-Supply-Depot",
        "Valley-Orchard-Main",
        "SouthRidge-FireStation",
        "Canyon-Grain-Coop",
        "MeadowBrook-Dairy",
        "Hilltop-Observatory",
        "RiverBend-Pumping",
        "OakWood-Res-35",
        "MapleGrove-Store",
    ]

    client_idx = 0
    for s_idx, sec in enumerate(sectors):
        ap_clients: list[dict[str, Any]] = []
        count = int(sec["client_count"])
        prefix = sec["subnet_prefix"]

        for c_offset in range(count):
            c_num = client_idx + 1
            mac = f"78:8A:20:9{s_idx + 1}:{c_offset + 10:02X}:{c_num:02X}"
            ip_host = 101 + c_offset
            cpe_ip = f"{prefix}.{ip_host}"
            cust_name = customer_names[client_idx % len(customer_names)]
            hostname = f"Loco5AC-{cust_name}"

            # Designate realistic RF profiles
            if c_offset == count - 1:
                # Weak signal client (< -75 dBm)
                chain0 = -77
                chain1 = -79
                signal = -78
                cap = 54
                qual = 62
                tx_rate = 117.0
                rx_rate = 104.0
                dist = 2450
            elif c_offset == count - 2:
                # High chain imbalance (>= 6 dB) due to misalignment / obstruction
                chain0 = -58
                chain1 = -66
                signal = -64
                cap = 63
                qual = 74
                tx_rate = 195.0
                rx_rate = 144.0
                dist = 1680
            elif c_offset == 0 and s_idx == 2:
                # Blocked MAC example
                chain0 = -61
                chain1 = -62
                signal = -62
                cap = 86
                qual = 91
                tx_rate = 300.0
                rx_rate = 300.0
                dist = 720
            else:
                # Healthy airMAX AC link
                chain0 = -54 - (c_offset % 10)
                chain1 = chain0 - (c_offset % 3)
                signal = min(chain0, chain1)
                cap = 84 + (c_offset % 13)
                qual = 88 + (c_offset % 10)
                tx_rate = 300.0 if signal > -64 else 240.0
                rx_rate = 300.0 if signal > -64 else 216.0
                dist = 380 + (c_offset * 145)

            is_blocked = bool(c_offset == 0 and s_idx == 2)
            tx_kbps = 0.0 if is_blocked else round(1850.0 + (c_offset * 940.5), 1)
            rx_kbps = 0.0 if is_blocked else round(420.0 + (c_offset * 310.2), 1)

            # Register the first 4 stations per sector as directly discovered managed Loco 5AC devices too
            if c_offset < 4:
                # Simulate historical IP drift on the very first station so IP history is immediately demonstrable
                if client_idx == 0:
                    repo.upsert_discovered_device(
                        {
                            "mac_address": mac,
                            "current_ip": f"{prefix}.188",
                            "hostname": hostname,
                            "model": "Loco 5AC",
                            "product_code": "NS-5ACL",
                            "role": "station",
                            "ssid": sec["ssid"],
                            "firmware_version": "WA.v8.7.11",
                            "frequency_mhz": sec["frequency_mhz"],
                            "channel_width_mhz": sec["channel_width_mhz"],
                            "tx_power_dbm": 19,
                            "noise_floor_dbm": -94,
                            "cpu_load_pct": 12.0,
                            "memory_used_pct": 36.0,
                            "uptime_sec": 604800,
                            "status": "online",
                            "discovery_source": "subnet_scan",
                        }
                    )
                repo.upsert_discovered_device(
                    {
                        "mac_address": mac,
                        "current_ip": cpe_ip,
                        "hostname": hostname,
                        "model": "Loco 5AC",
                        "product_code": "NS-5ACL",
                        "role": "station",
                        "ssid": sec["ssid"],
                        "firmware_version": "WA.v8.7.11",
                        "frequency_mhz": sec["frequency_mhz"],
                        "channel_width_mhz": sec["channel_width_mhz"],
                        "tx_power_dbm": 19,
                        "noise_floor_dbm": -94,
                        "cpu_load_pct": 14.5,
                        "memory_used_pct": 37.8,
                        "uptime_sec": 432000 + (c_offset * 3600),
                        "status": "online" if signal > -75 else "degraded",
                        "discovery_source": "router_dhcp" if client_idx == 0 else "subnet_scan",
                    }
                )

            ap_clients.append(
                {
                    "client_mac": mac,
                    "last_known_ip": cpe_ip,
                    "remote_hostname": hostname,
                    "remote_model": "Loco 5AC",
                    "remote_firmware": "WA.v8.7.11" if c_offset % 4 != 3 else "WA.v8.7.9",
                    "is_connected": not is_blocked,
                    "is_blocked": is_blocked,
                    "signal_dbm": signal,
                    "remote_signal_dbm": signal - 1,
                    "chain0_dbm": chain0,
                    "chain1_dbm": chain1,
                    "noise_floor_dbm": sec["noise_floor_dbm"],
                    "tx_rate_mbps": tx_rate,
                    "rx_rate_mbps": rx_rate,
                    "airmax_capacity_pct": cap,
                    "airmax_quality_pct": qual,
                    "distance_meters": dist,
                    "connection_uptime_sec": 345600 + (c_offset * 7200),
                    "tx_bytes": 8_450_000_000 + (c_offset * 1_250_000_000),
                    "rx_bytes": 2_120_000_000 + (c_offset * 410_000_000),
                    "tx_throughput_kbps": tx_kbps,
                    "rx_throughput_kbps": rx_kbps,
                    "tx_latency_ms": 1.8 if signal > -70 else 6.4,
                }
            )
            client_idx += 1

        sec_payload = dict(sec)
        sec_payload["tx_throughput_kbps"] = sum(c["tx_throughput_kbps"] for c in ap_clients)
        sec_payload["rx_throughput_kbps"] = sum(c["rx_throughput_kbps"] for c in ap_clients)
        sec_payload["clients"] = ap_clients
        repo.upsert_discovered_device(sec_payload)

    # Update subnet scan timestamps
    now = utc_now_iso()
    for sub in (s_north, s_east, s_south):
        devs_in_sub = repo.list_devices(subnet_id=sub["id"])
        repo._execute(
            "UPDATE subnets SET last_scanned_at = ?, last_discovered_count = ? WHERE id = ?",
            (now, len(devs_in_sub), sub["id"]),
        )

    # Record initial discovery audit task
    repo.create_task(
        task_type="scan_subnet",
        payload={"cidrs": ["10.10.10.0/24", "10.10.20.0/24", "172.16.40.0/24"], "mode": "hybrid_routed"},
        requested_by="system-agent",
        auto_complete_result={
            "discovered_aps": 4,
            "discovered_stations": 16,
            "associated_clients": 36,
            "duration_ms": 1840,
        },
    )

    return {"seeded": True, "aps": 4, "clients": client_idx}

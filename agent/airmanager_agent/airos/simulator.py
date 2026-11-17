from __future__ import annotations

"""
Built-in airOS 8 Radio & Sector Simulator for the Linux Network Agent.
Generates authentic airOS 8 `/status.cgi` and `/sta.cgi` JSON payloads for
LiteAP GPS sectors and Loco 5AC client stations across routed subnets.
"""

from typing import Any


def generate_simulated_airos_status(
    ip_address: str,
    mac_address: str,
    hostname: str,
    model: str = "LiteAP GPS",
    mode: str = "ap-ptmp",
    ssid: str = "AIRMAX-SECTOR-5G",
    frequency_mhz: int = 5745,
) -> dict[str, Any]:
    return {
        "host": {
            "hostname": hostname,
            "devmodel": model,
            "PrdID": "LAP-GPS" if "LiteAP" in model else "NS-5ACL",
            "fwversion": "WA.v8.7.11",
            "uptime": 1728000,
            "cpuload": 19.4,
            "totalram": 65536,
            "freeram": 36864,
        },
        "wireless": {
            "apmac": mac_address,
            "mode": mode,
            "essid": ssid,
            "frequency": f"{frequency_mhz} MHz",
            "chanbw": 40,
            "txpower": 22,
            "noisef": -94,
        },
        "gps": {
            "lat": 33.7124,
            "lon": 73.0651,
            "fix": 1,
        },
        "interfaces": [
            {"ifname": "ath0", "hwaddr": mac_address},
            {"ifname": "eth0", "hwaddr": mac_address},
        ],
    }


def generate_simulated_airos_sta_list(subnet_prefix: str = "10.10.10", count: int = 6) -> list[dict[str, Any]]:
    stations: list[dict[str, Any]] = []
    for i in range(count):
        mac = f"78:8A:20:91:{10 + i:02X}:{i + 1:02X}"
        sig = -56 - (i * 4)
        imb = 6 if i == count - 2 else 1
        stations.append(
            {
                "mac": mac,
                "lastip": f"{subnet_prefix}.{101 + i}",
                "signal": sig,
                "noisefloor": -94,
                "chain_rssi": [sig, sig - imb],
                "tx": 300.0 if sig > -68 else 144.0,
                "rx": 300.0 if sig > -68 else 130.0,
                "distance": 450 + (i * 220),
                "uptime": 120000 + (i * 3600),
                "tx_bytes": 5_000_000_000 + (i * 500_000_000),
                "rx_bytes": 1_200_000_000 + (i * 150_000_000),
                "tx_latency": 2.1,
                "airmax": {
                    "downlink_capacity": 88 if sig > -70 else 56,
                    "uplink_capacity": 84 if sig > -70 else 52,
                    "quality": 92 if sig > -70 else 64,
                },
                "remote": {
                    "hostname": f"Loco5AC-SimClient-{i + 1:02d}",
                    "platform": "NanoStation 5AC loco",
                    "version": "WA.v8.7.11",
                    "signal": sig - 1,
                    "ipaddr": f"{subnet_prefix}.{101 + i}",
                },
            }
        )
    return stations

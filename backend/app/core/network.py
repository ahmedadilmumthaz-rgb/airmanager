from __future__ import annotations

import ipaddress
import re


def normalize_mac(mac: str) -> str:
    """Normalizes any MAC string into uppercase colon-separated AA:BB:CC:DD:EE:FF."""
    cleaned = re.sub(r"[^0-9A-Fa-f]", "", mac or "")
    if len(cleaned) != 12:
        raise ValueError(f"Invalid MAC address: {mac!r}")
    pairs = [cleaned[i : i + 2].upper() for i in range(0, 12, 2)]
    return ":".join(pairs)


def validate_ip(ip_str: str) -> str:
    return str(ipaddress.ip_address(ip_str.strip()))


def validate_cidr(cidr_str: str) -> str:
    return str(ipaddress.ip_network(cidr_str.strip(), strict=False))


def ip_in_cidr(ip_str: str, cidr_str: str) -> bool:
    try:
        return ipaddress.ip_address(ip_str) in ipaddress.ip_network(cidr_str, strict=False)
    except ValueError:
        return False

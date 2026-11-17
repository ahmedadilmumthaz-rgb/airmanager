from __future__ import annotations

"""
Routed Multi-Subnet CIDR Scanner for Linux Network Agent.
Replaces Layer-2 UDP broadcast discovery with bounded-concurrency TCP reachability probing
across routed IPv4 CIDR blocks on management ports 443 and 80.
"""

import asyncio
from dataclasses import dataclass
import ipaddress
import time
from typing import Callable


@dataclass
class HostProbeResult:
    ip_address: str
    open_port: int
    latency_ms: float


def expand_cidr_hosts(cidr_block: str, max_hosts: int = 1024) -> list[str]:
    """Returns usable host IPs in an IPv4 CIDR block, capped at max_hosts for safety."""
    net = ipaddress.ip_network(cidr_block.strip(), strict=False)
    hosts = [str(ip) for ip in net.hosts()]
    if not hosts and net.num_addresses == 1:
        return [str(net.network_address)]
    return hosts[:max_hosts]


async def probe_tcp_port(ip_address: str, port: int, timeout_sec: float = 1.5) -> float | None:
    """Attempts an async TCP handshake to (ip_address, port). Returns latency_ms if open, else None."""
    start = time.monotonic()
    try:
        conn = asyncio.open_connection(ip_address, port)
        _reader, writer = await asyncio.wait_for(conn, timeout=timeout_sec)
        latency_ms = round((time.monotonic() - start) * 1000.0, 2)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return latency_ms
    except Exception:
        return None


class RoutedSubnetScanner:
    """Concurrent multi-subnet TCP reachability scanner."""

    def __init__(
        self,
        concurrency: int = 64,
        timeout_sec: float = 1.5,
        ports: tuple[int, ...] = (443, 80, 8080, 8443, 22),
        custom_prober: Callable[[str, int, float], asyncio.Future[float | None]] | None = None,
    ) -> None:
        self.concurrency = max(1, concurrency)
        self.timeout_sec = timeout_sec
        self.ports = ports
        self._prober = custom_prober or probe_tcp_port

    async def scan_cidr(self, cidr_block: str) -> list[HostProbeResult]:
        hosts = expand_cidr_hosts(cidr_block)
        sem = asyncio.Semaphore(self.concurrency)
        discovered: list[HostProbeResult] = []

        async def _check_host(ip_str: str) -> None:
            async with sem:
                for port in self.ports:
                    latency = await self._prober(ip_str, port, self.timeout_sec)
                    if latency is not None:
                        discovered.append(
                            HostProbeResult(
                                ip_address=ip_str,
                                open_port=port,
                                latency_ms=latency,
                            )
                        )
                        return

        await asyncio.gather(*(_check_host(h) for h in hosts))
        discovered.sort(key=lambda r: tuple(int(x) for x in r.ip_address.split(".")))
        return discovered

from __future__ import annotations

import os
import socket
from dataclasses import dataclass, field


@dataclass
class AgentConfig:
    agent_id: str = field(
        default_factory=lambda: os.getenv("AIRMANAGER_AGENT_ID", f"linux-agent-{socket.gethostname()}")
    )
    backend_url: str = field(
        default_factory=lambda: os.getenv("AIRMANAGER_BACKEND_URL", "http://127.0.0.1:8000")
    )
    agent_token: str = field(
        default_factory=lambda: os.getenv(
            "AIRMANAGER_AGENT_TOKEN",
            "airmanager-agent-shared-secret-token",
        )
    )
    scan_concurrency: int = field(
        default_factory=lambda: int(os.getenv("AIRMANAGER_SCAN_CONCURRENCY", "64"))
    )
    tcp_probe_timeout_sec: float = field(
        default_factory=lambda: float(os.getenv("AIRMANAGER_TCP_TIMEOUT_SEC", "1.5"))
    )
    poll_interval_sec: int = field(
        default_factory=lambda: int(os.getenv("AIRMANAGER_POLL_INTERVAL_SEC", "20"))
    )
    simulator_mode: bool = field(
        default_factory=lambda: os.getenv("AIRMANAGER_SIMULATOR_MODE", "false").lower() in ("1", "true", "yes")
    )
    default_airos_user: str = field(
        default_factory=lambda: os.getenv("AIRMANAGER_AIROS_USER", "ubnt")
    )
    default_airos_password: str = field(
        default_factory=lambda: os.getenv("AIRMANAGER_AIROS_PASSWORD", "ubnt")
    )


agent_config = AgentConfig()

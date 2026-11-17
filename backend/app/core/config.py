from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    project_name: str = "AirManager (Ubiquiti Network Manager)"
    version: str = "1.0.0"
    api_v1_prefix: str = "/api/v1"
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "AIRMANAGER_DATABASE_URL",
            "postgresql+psycopg2://airmanager:airmanager@127.0.0.1:5432/airmanager",
        )
    )
    master_key: str = field(
        default_factory=lambda: os.getenv(
            "AIRMANAGER_MASTER_KEY",
            "airmanager-default-32-byte-master-key-change-in-prod",
        )
    )
    agent_token: str = field(
        default_factory=lambda: os.getenv(
            "AIRMANAGER_AGENT_TOKEN",
            "airmanager-agent-shared-secret-token",
        )
    )
    admin_username: str = field(
        default_factory=lambda: os.getenv("AIRMANAGER_ADMIN_USER", "admin")
    )
    admin_password: str = field(
        default_factory=lambda: os.getenv("AIRMANAGER_ADMIN_PASSWORD", "ubnt-admin-2026")
    )
    auto_seed_demo: bool = field(
        default_factory=lambda: os.getenv("AIRMANAGER_AUTO_SEED", "true").lower() in ("1", "true", "yes")
    )
    cors_origins: list[str] = field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv(
                "AIRMANAGER_CORS_ORIGINS",
                "http://localhost:3002,http://127.0.0.1:3002,https://airmanager.ahmedadil.me",
            ).split(",")
            if origin.strip()
        ]
    )


settings = Settings()

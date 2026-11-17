"""Initial AirManager v1.0 PostgreSQL schema

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-11-17 22:30:00

"""
from __future__ import annotations

import os
from typing import Sequence, Union

from alembic import op

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    sql_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "deploy", "sql", "001_initial_schema.sql")
    )
    with open(sql_path, "r", encoding="utf-8") as f:
        op.execute(f.read())


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_tasks CASCADE;")
    op.execute("DROP TABLE IF EXISTS device_metrics CASCADE;")
    op.execute("DROP TABLE IF EXISTS wireless_clients CASCADE;")
    op.execute("DROP TABLE IF EXISTS device_ip_history CASCADE;")
    op.execute("DROP TABLE IF EXISTS devices CASCADE;")
    op.execute("DROP TABLE IF EXISTS routers CASCADE;")
    op.execute("DROP TABLE IF EXISTS subnets CASCADE;")
    op.execute("DROP TABLE IF EXISTS credential_profiles CASCADE;")

from __future__ import annotations

"""
SQLAlchemy 2.0 ORM Models for AirManager (PostgreSQL 16).
Matches deploy/sql/001_initial_schema.sql.
"""

from datetime import datetime, timezone
import uuid

try:
    from sqlalchemy import (
        BigInteger,
        Boolean,
        Column,
        DateTime,
        Float,
        ForeignKey,
        Index,
        Integer,
        LargeBinary,
        String,
        Text,
    )
    from sqlalchemy.dialects.postgresql import JSONB
    from sqlalchemy.orm import declarative_base, relationship

    Base = declarative_base()

    class CredentialProfileORM(Base):
        __tablename__ = "credential_profiles"

        id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        name = Column(String(120), nullable=False, unique=True)
        username = Column(String(120), nullable=False)
        encrypted_password = Column(LargeBinary, nullable=False)
        https_port = Column(Integer, nullable=False, default=443)
        is_default = Column(Boolean, nullable=False, default=False)
        created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
        updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    class SubnetORM(Base):
        __tablename__ = "subnets"

        id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        cidr_block = Column(String(43), nullable=False, unique=True)
        name = Column(String(120), nullable=False)
        site_name = Column(String(120), nullable=True)
        vlan_id = Column(Integer, nullable=True)
        scan_enabled = Column(Boolean, nullable=False, default=True)
        scan_interval_sec = Column(Integer, nullable=False, default=300)
        default_credential_id = Column(
            String(36), ForeignKey("credential_profiles.id", ondelete="SET NULL"), nullable=True
        )
        last_scanned_at = Column(DateTime(timezone=True), nullable=True)
        last_discovered_count = Column(Integer, nullable=False, default=0)
        created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    class RouterORM(Base):
        __tablename__ = "routers"

        id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        name = Column(String(120), nullable=False)
        host_ip = Column(String(45), nullable=False, unique=True)
        router_type = Column(String(32), nullable=False)  # edgerouter | unifi | uisp
        port = Column(Integer, nullable=False, default=22)
        credential_id = Column(
            String(36), ForeignKey("credential_profiles.id", ondelete="SET NULL"), nullable=True
        )
        enabled = Column(Boolean, nullable=False, default=True)
        last_synced_at = Column(DateTime(timezone=True), nullable=True)
        last_sync_status = Column(String(64), nullable=False, default="never")
        neighbors_found = Column(Integer, nullable=False, default=0)
        created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    class DeviceORM(Base):
        __tablename__ = "devices"

        id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        mac_address = Column(String(17), nullable=False, unique=True, index=True)
        current_ip = Column(String(45), nullable=False, index=True)
        hostname = Column(String(255), nullable=False)
        model = Column(String(64), nullable=False)
        product_code = Column(String(32), nullable=True)
        role = Column(String(24), nullable=False)  # ap | station | unknown
        ssid = Column(String(128), nullable=True)
        firmware_version = Column(String(64), nullable=True)
        frequency_mhz = Column(Integer, nullable=True)
        channel_width_mhz = Column(Integer, nullable=True)
        tx_power_dbm = Column(Integer, nullable=True)
        noise_floor_dbm = Column(Integer, nullable=True)
        cpu_load_pct = Column(Float, nullable=False, default=0.0)
        memory_used_pct = Column(Float, nullable=False, default=0.0)
        uptime_sec = Column(BigInteger, nullable=False, default=0)
        gps_lat = Column(Float, nullable=True)
        gps_lon = Column(Float, nullable=True)
        status = Column(String(24), nullable=False, default="online")
        credential_id = Column(
            String(36), ForeignKey("credential_profiles.id", ondelete="SET NULL"), nullable=True
        )
        subnet_id = Column(String(36), ForeignKey("subnets.id", ondelete="SET NULL"), nullable=True)
        first_discovered_at = Column(
            DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
        )
        last_seen_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

        ip_history = relationship("DeviceIpHistoryORM", back_populates="device", cascade="all, delete-orphan")
        clients = relationship(
            "WirelessClientORM",
            foreign_keys="WirelessClientORM.ap_device_id",
            back_populates="ap_device",
            cascade="all, delete-orphan",
        )

    class DeviceIpHistoryORM(Base):
        __tablename__ = "device_ip_history"

        id = Column(BigInteger, primary_key=True, autoincrement=True)
        device_id = Column(String(36), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
        ip_address = Column(String(45), nullable=False)
        subnet_cidr = Column(String(43), nullable=True)
        discovery_source = Column(String(32), nullable=False)
        first_seen_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
        last_seen_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

        device = relationship("DeviceORM", back_populates="ip_history")

    class WirelessClientORM(Base):
        __tablename__ = "wireless_clients"

        id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        ap_device_id = Column(String(36), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
        client_device_id = Column(String(36), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True)
        client_mac = Column(String(17), nullable=False, unique=True, index=True)
        last_known_ip = Column(String(45), nullable=True)
        remote_hostname = Column(String(255), nullable=True)
        remote_model = Column(String(64), nullable=False, default="Loco 5AC")
        remote_firmware = Column(String(64), nullable=True)
        is_connected = Column(Boolean, nullable=False, default=True)
        is_blocked = Column(Boolean, nullable=False, default=False)
        signal_dbm = Column(Integer, nullable=True)
        remote_signal_dbm = Column(Integer, nullable=True)
        chain0_dbm = Column(Integer, nullable=True)
        chain1_dbm = Column(Integer, nullable=True)
        chain_imbalance_db = Column(Integer, nullable=False, default=0)
        noise_floor_dbm = Column(Integer, nullable=True)
        snr_db = Column(Integer, nullable=True)
        tx_rate_mbps = Column(Float, nullable=True)
        rx_rate_mbps = Column(Float, nullable=True)
        airmax_capacity_pct = Column(Integer, nullable=True)
        airmax_quality_pct = Column(Integer, nullable=True)
        distance_meters = Column(Integer, nullable=True)
        connection_uptime_sec = Column(BigInteger, nullable=False, default=0)
        tx_bytes = Column(BigInteger, nullable=False, default=0)
        rx_bytes = Column(BigInteger, nullable=False, default=0)
        tx_throughput_kbps = Column(Float, nullable=False, default=0.0)
        rx_throughput_kbps = Column(Float, nullable=False, default=0.0)
        tx_latency_ms = Column(Float, nullable=False, default=0.0)
        first_associated_at = Column(
            DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
        )
        last_seen_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

        ap_device = relationship("DeviceORM", foreign_keys=[ap_device_id], back_populates="clients")

    class DeviceMetricORM(Base):
        __tablename__ = "device_metrics"

        id = Column(BigInteger, primary_key=True, autoincrement=True)
        device_id = Column(String(36), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
        recorded_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
        cpu_load_pct = Column(Float, nullable=True)
        memory_used_pct = Column(Float, nullable=True)
        connected_clients_count = Column(Integer, nullable=False, default=0)
        tx_throughput_kbps = Column(Float, nullable=False, default=0.0)
        rx_throughput_kbps = Column(Float, nullable=False, default=0.0)
        avg_client_signal_dbm = Column(Integer, nullable=True)
        noise_floor_dbm = Column(Integer, nullable=True)

        __table_args__ = (Index("idx_device_metrics_device_time", "device_id", "recorded_at"),)

    class AgentTaskORM(Base):
        __tablename__ = "agent_tasks"

        id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        task_type = Column(String(48), nullable=False)
        target_device_id = Column(String(36), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True)
        target_client_id = Column(
            String(36), ForeignKey("wireless_clients.id", ondelete="SET NULL"), nullable=True
        )
        payload = Column(JSONB, nullable=False, default=dict)
        status = Column(String(24), nullable=False, default="pending")
        result = Column(JSONB, nullable=True)
        error_message = Column(Text, nullable=True)
        requested_by = Column(String(120), nullable=False, default="admin")
        created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
        started_at = Column(DateTime(timezone=True), nullable=True)
        completed_at = Column(DateTime(timezone=True), nullable=True)

    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False
    Base = None  # type: ignore

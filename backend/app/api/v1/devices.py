from __future__ import annotations

"""
FastAPI Router for Devices & Sectors Inventory (/api/v1/devices/*).
"""

from typing import Any

from app.main import dispatcher

try:
    from fastapi import APIRouter, HTTPException

    router = APIRouter(prefix="/api/v1/devices", tags=["Devices & Sectors"])

    @router.get("")
    def list_devices(
        role: str | None = None,
        subnet_id: str | None = None,
        status: str | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        items = dispatcher.repo.list_devices(
            role=role,
            subnet_id=subnet_id,
            status=status,
            search=search,
        )
        return {"items": items, "total": len(items)}

    @router.get("/{device_id}")
    def get_device(device_id: str) -> dict[str, Any]:
        dev = dispatcher.repo.get_device_detail(device_id)
        if not dev:
            raise HTTPException(status_code=404, detail="Device not found")
        return dev

except ImportError:
    router = None  # type: ignore

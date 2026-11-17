from __future__ import annotations

"""
FastAPI Router for Connected Client Management (/api/v1/clients/*).
"""

from typing import Any

from app.main import dispatcher

try:
    from fastapi import APIRouter, HTTPException

    router = APIRouter(prefix="/api/v1/clients", tags=["Connected Clients"])

    @router.get("")
    def list_wireless_clients(
        ap_device_id: str | None = None,
        health_filter: str | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        clients = dispatcher.repo.list_clients(
            ap_device_id=ap_device_id,
            health_filter=health_filter,
            search=search,
        )
        return {"items": clients, "total": len(clients)}

    @router.get("/{client_id}")
    def get_wireless_client(client_id: str) -> dict[str, Any]:
        detail = dispatcher.repo.get_client_detail(client_id)
        if not detail:
            raise HTTPException(status_code=404, detail="Client not found")
        return detail

    @router.post("/{client_id}/kick")
    def kick_wireless_client(client_id: str) -> dict[str, Any]:
        code, resp = dispatcher.handle_request("POST", f"/api/v1/clients/{client_id}/kick")
        if code != 200:
            raise HTTPException(status_code=code, detail=resp.get("detail") if isinstance(resp, dict) else "Error")
        return resp  # type: ignore

    @router.post("/{client_id}/acl")
    def acl_wireless_client(client_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        code, resp = dispatcher.handle_request("POST", f"/api/v1/clients/{client_id}/acl", body=payload)
        if code != 200:
            raise HTTPException(status_code=code, detail=resp.get("detail") if isinstance(resp, dict) else "Error")
        return resp  # type: ignore

    @router.post("/{client_id}/reboot")
    def reboot_wireless_client(client_id: str) -> dict[str, Any]:
        code, resp = dispatcher.handle_request("POST", f"/api/v1/clients/{client_id}/reboot")
        if code != 200:
            raise HTTPException(status_code=code, detail=resp.get("detail") if isinstance(resp, dict) else "Error")
        return resp  # type: ignore

except ImportError:
    router = None  # type: ignore

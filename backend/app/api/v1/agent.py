from __future__ import annotations

"""
FastAPI Router for Linux Agent Protocol (/api/v1/agent/*).
"""

from typing import Any

from app.main import dispatcher

try:
    from fastapi import APIRouter, Header, HTTPException

    router = APIRouter(prefix="/api/v1/agent", tags=["Linux Network Agent"])

    @router.post("/heartbeat")
    def agent_heartbeat(
        payload: dict[str, Any],
        x_agent_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        code, resp = dispatcher.handle_request(
            "POST",
            "/api/v1/agent/heartbeat",
            body=payload,
            headers={"x-agent-token": x_agent_token or ""},
        )
        if code != 200:
            raise HTTPException(status_code=code, detail=resp.get("detail") if isinstance(resp, dict) else "Error")
        return resp  # type: ignore

    @router.post("/discovery-report")
    def agent_discovery_report(
        payload: dict[str, Any],
        x_agent_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        code, resp = dispatcher.handle_request(
            "POST",
            "/api/v1/agent/discovery-report",
            body=payload,
            headers={"x-agent-token": x_agent_token or ""},
        )
        if code != 200:
            raise HTTPException(status_code=code, detail=resp.get("detail") if isinstance(resp, dict) else "Error")
        return resp  # type: ignore

    @router.post("/telemetry-report")
    def agent_telemetry_report(
        payload: dict[str, Any],
        x_agent_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        code, resp = dispatcher.handle_request(
            "POST",
            "/api/v1/agent/telemetry-report",
            body=payload,
            headers={"x-agent-token": x_agent_token or ""},
        )
        if code != 200:
            raise HTTPException(status_code=code, detail=resp.get("detail") if isinstance(resp, dict) else "Error")
        return resp  # type: ignore

except ImportError:
    router = None  # type: ignore

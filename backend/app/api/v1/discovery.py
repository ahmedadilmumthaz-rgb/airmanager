from __future__ import annotations

"""
FastAPI Router for Subnets, Routers, and Credentials (/api/v1/subnets, /routers, /credentials).
"""

from typing import Any

from app.main import dispatcher

try:
    from fastapi import APIRouter

    router = APIRouter(prefix="/api/v1", tags=["Discovery & Subnets"])

    @router.get("/subnets")
    def list_subnets() -> dict[str, Any]:
        items = dispatcher.repo.list_subnets()
        return {"items": items, "total": len(items)}

    @router.get("/routers")
    def list_routers() -> dict[str, Any]:
        items = dispatcher.repo.list_routers()
        return {"items": items, "total": len(items)}

    @router.get("/credentials")
    def list_credentials() -> dict[str, Any]:
        items = dispatcher.repo.list_credentials(include_secret=False)
        return {"items": items, "total": len(items)}

except ImportError:
    router = None  # type: ignore

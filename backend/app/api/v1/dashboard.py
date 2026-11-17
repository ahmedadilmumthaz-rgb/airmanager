from __future__ import annotations

"""
FastAPI Router for Dashboard Overview (/api/v1/dashboard/summary).
"""

from typing import Any

from app.main import dispatcher

try:
    from fastapi import APIRouter

    router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])

    @router.get("/summary")
    def get_dashboard_summary() -> dict[str, Any]:
        return dispatcher.repo.get_dashboard_summary()

except ImportError:
    router = None  # type: ignore

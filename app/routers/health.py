"""Liveness / readiness endpoints (used by Docker healthcheck and supervision)."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("", summary="Liveness probe")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/db", summary="Readiness probe (database reachable)")
def health_db(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "reachable"}

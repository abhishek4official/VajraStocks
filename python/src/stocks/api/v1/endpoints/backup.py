"""Backup/restore API (V2.0 spec M8) — export/import irreplaceable user data."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from stocks.api.deps import get_db
from stocks.services.backup import export_user_data, import_user_data

router = APIRouter(prefix="/backup", tags=["Backup"])


@router.get("/export")
def export_backup(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Export journal trades, watchlists, and pick notes as a portable JSON document."""
    return export_user_data(db)


@router.post("/import")
def import_backup(data: dict[str, Any] = Body(...), db: Session = Depends(get_db)) -> dict[str, int]:
    """Restore a previously-exported backup (idempotent). Returns counts of new records."""
    return import_user_data(db, data)

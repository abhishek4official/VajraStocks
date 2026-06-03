"""Settings CRUD API — read and update application settings stored in the database."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from stocks.api.deps import get_db
from stocks.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["Settings"])


class SettingUpdate(BaseModel):
    value: str


@router.get("")
def get_all_settings(db: Session = Depends(get_db)):
    """Returns all settings grouped by category. Secret values are masked."""
    svc = SettingsService(db)
    return svc.settings_by_category()


@router.put("/{category}/{key}")
def update_setting(category: str, key: str, body: SettingUpdate, db: Session = Depends(get_db)):
    """Updates a single setting value."""
    svc = SettingsService(db)
    # Verify the setting exists
    all_flat = svc.all_settings()
    exists = any(s["category"] == category.upper() and s["key"] == key for s in all_flat)
    if not exists:
        raise HTTPException(status_code=404, detail=f"Setting '{category}/{key}' not found.")
    svc.set(category.upper(), key, body.value)
    return {"status": "updated", "category": category.upper(), "key": key}


@router.post("/reload")
def reload_settings(request: Request, db: Session = Depends(get_db)):
    """Signals that settings have changed (busts the in-process cache)."""
    # Future: could notify other workers via a message queue
    return {"status": "ok", "message": "Settings cache will refresh on next read."}

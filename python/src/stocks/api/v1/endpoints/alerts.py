from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from stocks.api.deps import get_db
from stocks.services.alert_service import AlertService

router = APIRouter(prefix="/alerts", tags=["Alerts"])


class AlertResponse(BaseModel):
    id: int
    symbol: str
    alert_type: str
    condition_value: float | None = None
    status: str
    scope: str
    message: str
    triggered_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=list[AlertResponse])
def list_alerts(
    status: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Returns triggered/dismissed alerts, newest first."""
    svc = AlertService(db)
    return svc.get_alerts(status=status, limit=limit)


@router.post("/{alert_id}/dismiss", response_model=dict)
def dismiss_alert(alert_id: int, db: Session = Depends(get_db)):
    """Marks a single alert as dismissed."""
    svc = AlertService(db)
    if not svc.dismiss(alert_id):
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"dismissed": True}


@router.post("/dismiss-all", response_model=dict)
def dismiss_all_alerts(db: Session = Depends(get_db)):
    """Marks all triggered alerts as dismissed."""
    svc = AlertService(db)
    count = svc.dismiss_all()
    return {"dismissed": count}


@router.post("/evaluate", response_model=dict)
def run_evaluation(db: Session = Depends(get_db)):
    """Manually triggers an alert evaluation pass (useful for testing)."""
    svc = AlertService(db)
    count = svc.evaluate_all()
    return {"new_alerts": count}

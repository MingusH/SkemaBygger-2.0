from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.timeslot import TimeSlot
from app.schemas.timeslot import TimeSlotCreate, TimeSlotUpdate, TimeSlotRead
from app.routers._deps import require_school_admin, require_school_member

router = APIRouter(prefix="/schools/{school_id}/timeslots", tags=["timeslots"])


@router.get("", response_model=list[TimeSlotRead])
def list_timeslots(school_id: int, db: Session = Depends(get_db), _=Depends(require_school_member)):
    return (
        db.query(TimeSlot)
        .filter(TimeSlot.school_id == school_id)
        .order_by(TimeSlot.day_of_week, TimeSlot.period_number)
        .all()
    )


@router.post("", response_model=TimeSlotRead, status_code=201)
def create_timeslot(school_id: int, body: TimeSlotCreate, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    ts = TimeSlot(school_id=school_id, **body.model_dump())
    db.add(ts)
    db.commit()
    db.refresh(ts)
    return ts


@router.post("/bulk", response_model=list[TimeSlotRead], status_code=201)
def create_timeslots_bulk(school_id: int, body: list[TimeSlotCreate], db: Session = Depends(get_db), _=Depends(require_school_admin)):
    """Create multiple time slots at once (e.g., full week setup)."""
    slots = [TimeSlot(school_id=school_id, **s.model_dump()) for s in body]
    db.add_all(slots)
    db.commit()
    for s in slots:
        db.refresh(s)
    return slots


@router.patch("/{slot_id}", response_model=TimeSlotRead)
def update_timeslot(school_id: int, slot_id: int, body: TimeSlotUpdate, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    ts = db.query(TimeSlot).filter(TimeSlot.id == slot_id, TimeSlot.school_id == school_id).first()
    if not ts:
        raise HTTPException(404, "Time slot not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(ts, k, v)
    db.commit()
    db.refresh(ts)
    return ts


@router.delete("/{slot_id}", status_code=204)
def delete_timeslot(school_id: int, slot_id: int, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    ts = db.query(TimeSlot).filter(TimeSlot.id == slot_id, TimeSlot.school_id == school_id).first()
    if not ts:
        raise HTTPException(404, "Time slot not found")
    db.delete(ts)
    db.commit()

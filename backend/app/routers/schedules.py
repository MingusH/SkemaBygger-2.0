from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.schedule import Schedule, ScheduleEntry, ScheduleStatus
from app.schemas.schedule import ScheduleCreate, ScheduleRead, ScheduleEntryRead
from app.routers._deps import require_school_admin, require_school_member

router = APIRouter(prefix="/schools/{school_id}/schedules", tags=["schedules"])


@router.get("", response_model=list[ScheduleRead])
def list_schedules(school_id: int, db: Session = Depends(get_db), _=Depends(require_school_member)):
    return db.query(Schedule).filter(Schedule.school_id == school_id).all()


@router.post("", response_model=ScheduleRead, status_code=201)
def create_schedule(school_id: int, body: ScheduleCreate, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    s = Schedule(school_id=school_id, **body.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.get("/{schedule_id}", response_model=ScheduleRead)
def get_schedule(school_id: int, schedule_id: int, db: Session = Depends(get_db), _=Depends(require_school_member)):
    s = db.query(Schedule).filter(Schedule.id == schedule_id, Schedule.school_id == school_id).first()
    if not s:
        raise HTTPException(404, "Schedule not found")
    return s


@router.delete("/{schedule_id}", status_code=204)
def delete_schedule(school_id: int, schedule_id: int, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    s = db.query(Schedule).filter(Schedule.id == schedule_id, Schedule.school_id == school_id).first()
    if not s:
        raise HTTPException(404, "Schedule not found")
    db.delete(s)
    db.commit()


@router.post("/{schedule_id}/generate", response_model=ScheduleRead)
def generate_schedule(
    school_id: int,
    schedule_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _=Depends(require_school_admin),
):
    """Trigger OR-Tools solver in the background. Returns immediately with GENERATING status."""
    from app.services import validation as val_service, solver as solver_service

    s = db.query(Schedule).filter(Schedule.id == schedule_id, Schedule.school_id == school_id).first()
    if not s:
        raise HTTPException(404, "Schedule not found")

    result = val_service.validate_school(school_id, db)
    if not result.is_valid:
        raise HTTPException(422, detail={"message": "Validation failed", "errors": [e.model_dump() for e in result.errors]})

    s.status = ScheduleStatus.GENERATING
    db.commit()

    background_tasks.add_task(solver_service.run_solver, schedule_id)
    db.refresh(s)
    return s


@router.get("/{schedule_id}/entries", response_model=list[ScheduleEntryRead])
def get_entries(school_id: int, schedule_id: int, db: Session = Depends(get_db), _=Depends(require_school_member)):
    return db.query(ScheduleEntry).filter(ScheduleEntry.schedule_id == schedule_id).all()


@router.patch("/{schedule_id}/entries/{entry_id}/lock", response_model=ScheduleEntryRead)
def toggle_lock(school_id: int, schedule_id: int, entry_id: int, locked: bool, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    entry = db.query(ScheduleEntry).filter(ScheduleEntry.id == entry_id, ScheduleEntry.schedule_id == schedule_id).first()
    if not entry:
        raise HTTPException(404, "Entry not found")
    entry.is_locked = locked
    db.commit()
    db.refresh(entry)
    return entry

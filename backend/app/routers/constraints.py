from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.constraints import TeacherUnavailability, RoomUnavailability, ClassUnavailability, SchedulingPreference
from app.schemas.constraints import (
    TeacherUnavailabilityCreate, TeacherUnavailabilityRead,
    RoomUnavailabilityCreate, RoomUnavailabilityRead,
    ClassUnavailabilityCreate, ClassUnavailabilityRead,
    SchedulingPreferenceCreate, SchedulingPreferenceRead,
)
from app.routers._deps import require_school_admin, require_school_member

router = APIRouter(tags=["constraints"])


# --- Teacher unavailabilities ---

@router.get("/schools/{school_id}/teachers/{teacher_id}/unavailabilities", response_model=list[TeacherUnavailabilityRead])
def list_teacher_unavailabilities(school_id: int, teacher_id: int, db: Session = Depends(get_db), _=Depends(require_school_member)):
    return db.query(TeacherUnavailability).filter(TeacherUnavailability.teacher_id == teacher_id).all()


@router.post("/schools/{school_id}/teachers/{teacher_id}/unavailabilities", response_model=TeacherUnavailabilityRead, status_code=201)
def add_teacher_unavailability(school_id: int, teacher_id: int, body: TeacherUnavailabilityCreate, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    u = TeacherUnavailability(teacher_id=teacher_id, **body.model_dump())
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@router.delete("/schools/{school_id}/teachers/{teacher_id}/unavailabilities/{unavail_id}", status_code=204)
def delete_teacher_unavailability(school_id: int, teacher_id: int, unavail_id: int, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    u = db.query(TeacherUnavailability).filter(TeacherUnavailability.id == unavail_id, TeacherUnavailability.teacher_id == teacher_id).first()
    if not u:
        raise HTTPException(404, "Not found")
    db.delete(u)
    db.commit()


# --- Room unavailabilities ---

@router.get("/schools/{school_id}/rooms/{room_id}/unavailabilities", response_model=list[RoomUnavailabilityRead])
def list_room_unavailabilities(school_id: int, room_id: int, db: Session = Depends(get_db), _=Depends(require_school_member)):
    return db.query(RoomUnavailability).filter(RoomUnavailability.room_id == room_id).all()


@router.post("/schools/{school_id}/rooms/{room_id}/unavailabilities", response_model=RoomUnavailabilityRead, status_code=201)
def add_room_unavailability(school_id: int, room_id: int, body: RoomUnavailabilityCreate, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    u = RoomUnavailability(room_id=room_id, **body.model_dump())
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@router.delete("/schools/{school_id}/rooms/{room_id}/unavailabilities/{unavail_id}", status_code=204)
def delete_room_unavailability(school_id: int, room_id: int, unavail_id: int, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    u = db.query(RoomUnavailability).filter(RoomUnavailability.id == unavail_id, RoomUnavailability.room_id == room_id).first()
    if not u:
        raise HTTPException(404, "Not found")
    db.delete(u)
    db.commit()


# --- Class unavailabilities ---

@router.get("/schools/{school_id}/classes/{class_id}/unavailabilities", response_model=list[ClassUnavailabilityRead])
def list_class_unavailabilities(school_id: int, class_id: int, db: Session = Depends(get_db), _=Depends(require_school_member)):
    return db.query(ClassUnavailability).filter(ClassUnavailability.student_class_id == class_id).all()


@router.post("/schools/{school_id}/classes/{class_id}/unavailabilities", response_model=ClassUnavailabilityRead, status_code=201)
def add_class_unavailability(school_id: int, class_id: int, body: ClassUnavailabilityCreate, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    u = ClassUnavailability(student_class_id=class_id, **body.model_dump())
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@router.delete("/schools/{school_id}/classes/{class_id}/unavailabilities/{unavail_id}", status_code=204)
def delete_class_unavailability(school_id: int, class_id: int, unavail_id: int, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    u = db.query(ClassUnavailability).filter(ClassUnavailability.id == unavail_id, ClassUnavailability.student_class_id == class_id).first()
    if not u:
        raise HTTPException(404, "Not found")
    db.delete(u)
    db.commit()


# --- Scheduling preferences ---

@router.get("/schools/{school_id}/preferences", response_model=list[SchedulingPreferenceRead])
def list_preferences(school_id: int, db: Session = Depends(get_db), _=Depends(require_school_member)):
    return db.query(SchedulingPreference).filter(SchedulingPreference.school_id == school_id).all()


@router.post("/schools/{school_id}/preferences", response_model=SchedulingPreferenceRead, status_code=201)
def add_preference(school_id: int, body: SchedulingPreferenceCreate, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    p = SchedulingPreference(school_id=school_id, **body.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.delete("/schools/{school_id}/preferences/{pref_id}", status_code=204)
def delete_preference(school_id: int, pref_id: int, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    p = db.query(SchedulingPreference).filter(SchedulingPreference.id == pref_id, SchedulingPreference.school_id == school_id).first()
    if not p:
        raise HTTPException(404, "Not found")
    db.delete(p)
    db.commit()

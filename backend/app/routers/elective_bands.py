from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.school import School
from app.models.elective import ElectiveBand, ElectiveOffering
from app.models.student_class import StudentClass
from app.models.room import Room
from app.schemas.elective import (
    ElectiveBandCreate, ElectiveBandUpdate, ElectiveBandRead,
    ElectiveOfferingCreate, ElectiveOfferingRead,
)
from app.routers._deps import require_school_member, require_school_admin

router = APIRouter(prefix="/schools/{school_id}/elective-bands", tags=["elective-bands"])


def _get_band(db: Session, school_id: int, band_id: int) -> ElectiveBand:
    band = db.query(ElectiveBand).filter(
        ElectiveBand.id == band_id, ElectiveBand.school_id == school_id
    ).first()
    if not band:
        raise HTTPException(404, "Elective band not found")
    return band


def _validate_offering_room(db: Session, school_id: int, band: ElectiveBand, room_id: int):
    room = db.query(Room).filter(Room.id == room_id, Room.school_id == school_id).first()
    if not room:
        raise HTTPException(422, "Room not found in this school")
    # A class home room can't host an elective offering (it competes with ordinary lessons).
    home = db.query(StudentClass).filter(
        StudentClass.school_id == school_id, StudentClass.home_room_id == room_id
    ).first()
    if home:
        raise HTTPException(422, f"Room {room.name} is a class home room and can't host an offering")
    # No two offerings of the same band may share a room (they run simultaneously).
    if any(o.room_id == room_id for o in band.offerings):
        raise HTTPException(422, f"Room {room.name} is already used by another offering in this band")


@router.get("", response_model=list[ElectiveBandRead])
def list_bands(school_id: int, db: Session = Depends(get_db), _=Depends(require_school_member)):
    return (
        db.query(ElectiveBand)
        .filter(ElectiveBand.school_id == school_id)
        .order_by(ElectiveBand.grade_level, ElectiveBand.name)
        .all()
    )


@router.post("", response_model=ElectiveBandRead, status_code=201)
def create_band(school_id: int, body: ElectiveBandCreate, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    school = db.get(School, school_id)
    if not school:
        raise HTTPException(404, "School not found")

    band = ElectiveBand(
        school_id=school_id,
        grade_level=body.grade_level,
        band_type=body.band_type,
        name=body.name,
        hours_per_week=body.hours_per_week,
        requires_consecutive=body.requires_consecutive,
        draws_timebank=body.draws_timebank,
        academic_year=school.academic_year,
    )
    db.add(band)
    db.flush()  # need band.id for offering validation

    seen_rooms: set[int] = set()
    for off in body.offerings:
        if off.room_id in seen_rooms:
            raise HTTPException(422, "Two offerings can't share the same room")
        _validate_offering_room(db, school_id, band, off.room_id)
        db.add(ElectiveOffering(band_id=band.id, subject_id=off.subject_id, teacher_id=off.teacher_id, room_id=off.room_id))
        seen_rooms.add(off.room_id)

    db.commit()
    db.refresh(band)
    return band


@router.patch("/{band_id}", response_model=ElectiveBandRead)
def update_band(school_id: int, band_id: int, body: ElectiveBandUpdate, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    band = _get_band(db, school_id, band_id)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(band, k, v)
    db.commit()
    db.refresh(band)
    return band


@router.delete("/{band_id}", status_code=204)
def delete_band(school_id: int, band_id: int, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    band = _get_band(db, school_id, band_id)
    db.delete(band)
    db.commit()


@router.post("/{band_id}/offerings", response_model=ElectiveOfferingRead, status_code=201)
def add_offering(school_id: int, band_id: int, body: ElectiveOfferingCreate, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    band = _get_band(db, school_id, band_id)
    _validate_offering_room(db, school_id, band, body.room_id)
    off = ElectiveOffering(band_id=band.id, subject_id=body.subject_id, teacher_id=body.teacher_id, room_id=body.room_id)
    db.add(off)
    db.commit()
    db.refresh(off)
    return off


@router.delete("/{band_id}/offerings/{offering_id}", status_code=204)
def delete_offering(school_id: int, band_id: int, offering_id: int, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    band = _get_band(db, school_id, band_id)
    off = db.query(ElectiveOffering).filter(
        ElectiveOffering.id == offering_id, ElectiveOffering.band_id == band.id
    ).first()
    if not off:
        raise HTTPException(404, "Offering not found")
    db.delete(off)
    db.commit()

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.school import School
from app.models.subject import Subject
from app.schemas.subject import SubjectRead, SubjectCreate, SubjectUpdate
from app.routers._deps import require_school_member, require_school_admin

router = APIRouter(prefix="/schools/{school_id}/subjects", tags=["subjects"])


@router.get("", response_model=list[SubjectRead])
def list_subjects(school_id: int, db: Session = Depends(get_db), _=Depends(require_school_member)):
    return (
        db.query(Subject)
        .filter(Subject.school_id == school_id)
        .order_by(Subject.priority, Subject.name)
        .all()
    )


@router.post("", response_model=SubjectRead, status_code=201)
def create_subject(school_id: int, body: SubjectCreate, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    if not db.get(School, school_id):
        raise HTTPException(404, "School not found")
    if db.query(Subject).filter(Subject.school_id == school_id, Subject.name == body.name).first():
        raise HTTPException(422, f"A subject named '{body.name}' already exists")

    subj = Subject(
        school_id=school_id,
        name=body.name,
        short_code=body.short_code,
        category=body.category,
        color_hex=body.color_hex,
        required_room_type=body.required_room_type,
        requires_special_room=body.required_room_type is not None,
        double_lessons=body.double_lessons,
        is_elective_slot=False,
        priority=body.priority,
    )
    db.add(subj)
    db.commit()
    db.refresh(subj)
    return subj


@router.get("/{subject_id}", response_model=SubjectRead)
def get_subject(school_id: int, subject_id: int, db: Session = Depends(get_db), _=Depends(require_school_member)):
    subj = db.query(Subject).filter(Subject.id == subject_id, Subject.school_id == school_id).first()
    if not subj:
        raise HTTPException(404, "Subject not found")
    return subj


@router.patch("/{subject_id}", response_model=SubjectRead)
def update_subject(school_id: int, subject_id: int, body: SubjectUpdate, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    subj = db.query(Subject).filter(Subject.id == subject_id, Subject.school_id == school_id).first()
    if not subj:
        raise HTTPException(404, "Subject not found")
    data = body.model_dump(exclude_unset=True)
    # Setting a required room type implies the subject needs a special room
    if data.get("required_room_type") is not None:
        data.setdefault("requires_special_room", True)
    for k, v in data.items():
        setattr(subj, k, v)
    db.commit()
    db.refresh(subj)
    return subj

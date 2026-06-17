from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.teacher import Teacher, TeacherSubject
from app.schemas.teacher import TeacherCreate, TeacherUpdate, TeacherRead, TeacherSubjectCreate
from app.routers._deps import require_school_admin, require_school_member

router = APIRouter(prefix="/schools/{school_id}/teachers", tags=["teachers"])


@router.get("", response_model=list[TeacherRead])
def list_teachers(school_id: int, db: Session = Depends(get_db), _=Depends(require_school_member)):
    teachers = db.query(Teacher).filter(Teacher.school_id == school_id).all()
    for t in teachers:
        t.subject_ids = [ts.subject_id for ts in t.teacher_subjects]
    return teachers


@router.post("", response_model=TeacherRead, status_code=201)
def create_teacher(school_id: int, body: TeacherCreate, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    data = body.model_dump(exclude={"subject_ids"})
    teacher = Teacher(school_id=school_id, **data)
    db.add(teacher)
    db.flush()
    for sid in body.subject_ids:
        db.add(TeacherSubject(teacher_id=teacher.id, subject_id=sid))
    db.commit()
    db.refresh(teacher)
    teacher.subject_ids = [ts.subject_id for ts in teacher.teacher_subjects]
    return teacher


@router.get("/{teacher_id}", response_model=TeacherRead)
def get_teacher(school_id: int, teacher_id: int, db: Session = Depends(get_db), _=Depends(require_school_member)):
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id, Teacher.school_id == school_id).first()
    if not teacher:
        raise HTTPException(404, "Teacher not found")
    teacher.subject_ids = [ts.subject_id for ts in teacher.teacher_subjects]
    return teacher


@router.patch("/{teacher_id}", response_model=TeacherRead)
def update_teacher(school_id: int, teacher_id: int, body: TeacherUpdate, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id, Teacher.school_id == school_id).first()
    if not teacher:
        raise HTTPException(404, "Teacher not found")
    data = body.model_dump(exclude_none=True)
    subject_ids = data.pop("subject_ids", None)
    for k, v in data.items():
        setattr(teacher, k, v)
    if subject_ids is not None:
        # Replace qualifications wholesale with the provided set.
        db.query(TeacherSubject).filter(TeacherSubject.teacher_id == teacher.id).delete()
        for sid in subject_ids:
            db.add(TeacherSubject(teacher_id=teacher.id, subject_id=sid))
    db.commit()
    db.refresh(teacher)
    teacher.subject_ids = [ts.subject_id for ts in teacher.teacher_subjects]
    return teacher


@router.delete("/{teacher_id}", status_code=204)
def delete_teacher(school_id: int, teacher_id: int, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id, Teacher.school_id == school_id).first()
    if not teacher:
        raise HTTPException(404, "Teacher not found")
    db.delete(teacher)
    db.commit()


# --- Subject qualifications ---

@router.post("/{teacher_id}/subjects", status_code=201)
def add_subject(school_id: int, teacher_id: int, body: TeacherSubjectCreate, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    if db.query(TeacherSubject).filter_by(teacher_id=teacher_id, subject_id=body.subject_id).first():
        raise HTTPException(409, "Qualification already exists")
    db.add(TeacherSubject(teacher_id=teacher_id, subject_id=body.subject_id))
    db.commit()
    return {"teacher_id": teacher_id, "subject_id": body.subject_id}


@router.delete("/{teacher_id}/subjects/{subject_id}", status_code=204)
def remove_subject(school_id: int, teacher_id: int, subject_id: int, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    ts = db.query(TeacherSubject).filter_by(teacher_id=teacher_id, subject_id=subject_id).first()
    if not ts:
        raise HTTPException(404, "Qualification not found")
    db.delete(ts)
    db.commit()

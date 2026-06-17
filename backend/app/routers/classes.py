from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.student_class import StudentClass
from app.schemas.student_class import StudentClassCreate, StudentClassUpdate, StudentClassRead, BulkClassCreate
from app.routers._deps import require_school_admin, require_school_member

router = APIRouter(prefix="/schools/{school_id}/classes", tags=["classes"])


@router.get("", response_model=list[StudentClassRead])
def list_classes(school_id: int, db: Session = Depends(get_db), _=Depends(require_school_member)):
    return db.query(StudentClass).filter(StudentClass.school_id == school_id).all()


@router.post("/bulk", response_model=list[StudentClassRead], status_code=201)
def bulk_create_classes(school_id: int, body: BulkClassCreate, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    created = []
    for grade in range(body.grade_start, body.grade_end + 1):
        for suffix in body.suffixes:
            sc = StudentClass(
                school_id=school_id,
                name=f"{grade}{suffix.strip()}",
                grade_level=grade,
                student_count=body.student_count,
            )
            db.add(sc)
            created.append(sc)
    db.commit()
    for sc in created:
        db.refresh(sc)
    return created


@router.post("", response_model=StudentClassRead, status_code=201)
def create_class(school_id: int, body: StudentClassCreate, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    sc = StudentClass(school_id=school_id, **body.model_dump())
    db.add(sc)
    db.commit()
    db.refresh(sc)
    return sc


@router.get("/{class_id}", response_model=StudentClassRead)
def get_class(school_id: int, class_id: int, db: Session = Depends(get_db), _=Depends(require_school_member)):
    sc = db.query(StudentClass).filter(StudentClass.id == class_id, StudentClass.school_id == school_id).first()
    if not sc:
        raise HTTPException(404, "Class not found")
    return sc


@router.patch("/{class_id}", response_model=StudentClassRead)
def update_class(school_id: int, class_id: int, body: StudentClassUpdate, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    sc = db.query(StudentClass).filter(StudentClass.id == class_id, StudentClass.school_id == school_id).first()
    if not sc:
        raise HTTPException(404, "Class not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(sc, k, v)
    db.commit()
    db.refresh(sc)
    return sc


@router.delete("/{class_id}", status_code=204)
def delete_class(school_id: int, class_id: int, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    sc = db.query(StudentClass).filter(StudentClass.id == class_id, StudentClass.school_id == school_id).first()
    if not sc:
        raise HTTPException(404, "Class not found")
    db.delete(sc)
    db.commit()

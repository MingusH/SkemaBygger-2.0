from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.school import School
from app.models.user import User, SchoolMember, UserRole
from app.schemas.school import SchoolCreate, SchoolUpdate, SchoolRead
from app.schemas.user import SchoolMemberRead, SchoolMemberCreate
from app.schemas.validation import ValidationResult
from app.routers.auth import get_current_user
from app.routers._deps import require_school_admin, require_school_member
from app.services import validation as val_service, seed as seed_service

router = APIRouter(prefix="/schools", tags=["schools"])


@router.post("", response_model=SchoolRead, status_code=201)
def create_school(
    body: SchoolCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school = School(**body.model_dump())
    db.add(school)
    db.flush()
    # Creator becomes admin
    member = SchoolMember(school_id=school.id, user_id=current_user.id, role=UserRole.ADMIN)
    db.add(member)
    db.commit()
    db.refresh(school)
    return school


@router.get("", response_model=list[SchoolRead])
def list_schools(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.is_superadmin:
        return db.query(School).all()
    ids = [m.school_id for m in current_user.school_memberships]
    return db.query(School).filter(School.id.in_(ids)).all()


@router.get("/{school_id}", response_model=SchoolRead)
def get_school(school_id: int, db: Session = Depends(get_db), _=Depends(require_school_member)):
    return db.get(School, school_id)


@router.patch("/{school_id}", response_model=SchoolRead)
def update_school(school_id: int, body: SchoolUpdate, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    school = db.get(School, school_id)
    if not school:
        raise HTTPException(404, "School not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(school, k, v)
    db.commit()
    db.refresh(school)
    return school


@router.delete("/{school_id}", status_code=204)
def delete_school(school_id: int, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    school = db.get(School, school_id)
    if not school:
        raise HTTPException(404, "School not found")
    db.delete(school)
    db.commit()


# --- Members ---

@router.get("/{school_id}/members", response_model=list[SchoolMemberRead])
def list_members(school_id: int, db: Session = Depends(get_db), _=Depends(require_school_member)):
    return db.query(SchoolMember).filter(SchoolMember.school_id == school_id).all()


@router.post("/{school_id}/members", response_model=SchoolMemberRead, status_code=201)
def add_member(school_id: int, body: SchoolMemberCreate, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    member = SchoolMember(school_id=school_id, **body.model_dump())
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


# --- Seed subjects from ministry PDF ---

@router.post("/{school_id}/seed-subjects", status_code=200)
def seed_subjects(
    school_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_school_admin),
):
    """Populate subjects from the Danish ministry PDF. Safe to run multiple times (idempotent)."""
    count = seed_service.seed_subjects_for_school(school_id, db)
    return {"seeded": count, "message": f"Seeded {count} subjects from ministry data"}


# --- Validation ---

@router.post("/{school_id}/validate", response_model=ValidationResult)
def validate(school_id: int, db: Session = Depends(get_db), _=Depends(require_school_member)):
    return val_service.validate_school(school_id, db)

"""Shared router dependencies."""
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, SchoolMember, UserRole
from app.models.school import School
from app.routers.auth import get_current_user


def get_school_or_404(school_id: int, db: Session = Depends(get_db)) -> School:
    school = db.get(School, school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    return school


def require_school_admin(
    school_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.is_superadmin:
        return current_user
    member = (
        db.query(SchoolMember)
        .filter(SchoolMember.school_id == school_id, SchoolMember.user_id == current_user.id)
        .first()
    )
    if not member or member.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="School admin role required")
    return current_user


def require_school_member(
    school_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.is_superadmin:
        return current_user
    member = (
        db.query(SchoolMember)
        .filter(SchoolMember.school_id == school_id, SchoolMember.user_id == current_user.id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this school")
    return current_user

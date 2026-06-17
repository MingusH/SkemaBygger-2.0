"""
Validation rule tests (V1-V8 blockers and basic warnings).
"""
import pytest

from app.services.validation import validate_school
from app.models.teacher import TeacherSubject
from app.models.timeslot import TimeSlot


def test_valid_school_passes(db, minimal_school):
    result = validate_school(minimal_school["school"].id, db)
    assert result.is_valid, f"Expected valid school, got errors: {[e.message for e in result.errors]}"


def test_missing_timeslots_fails_v6(db, minimal_school):
    """Deleting one slot breaks the grid — V6 should fire."""
    db.delete(minimal_school["slots"][0])
    db.commit()
    result = validate_school(minimal_school["school"].id, db)
    assert not result.is_valid
    assert any(e.rule == "V6" for e in result.errors), f"Expected V6, got: {[e.rule for e in result.errors]}"


def test_unqualified_teacher_fails_v2(db, minimal_school):
    """Removing a qualification while keeping the assignment triggers V2."""
    qual = db.query(TeacherSubject).filter_by(
        teacher_id=minimal_school["teacher"].id,
        subject_id=minimal_school["subjects"][0].id,
    ).first()
    db.delete(qual)
    db.commit()
    result = validate_school(minimal_school["school"].id, db)
    assert not result.is_valid
    assert any(e.rule == "V2" for e in result.errors), f"Expected V2, got: {[e.rule for e in result.errors]}"


def test_over_capacity_class_fails_v3(db, minimal_school):
    """A class with total hours > available slots (35) should fail V3."""
    # Give one assignment enough hours to overflow
    a = minimal_school["assignments"][0]
    a.hours_per_week = 34  # class total becomes 34 + 2 = 36 > 35
    db.commit()
    result = validate_school(minimal_school["school"].id, db)
    assert not result.is_valid
    assert any(e.rule == "V3" for e in result.errors), f"Expected V3, got: {[e.rule for e in result.errors]}"


def test_no_rooms_fails_v8(db, minimal_school):
    """A school without rooms should fail V8."""
    for r in minimal_school["rooms"]:
        r.is_active = False
    db.commit()
    result = validate_school(minimal_school["school"].id, db)
    assert not result.is_valid
    assert any(e.rule == "V8" for e in result.errors)


def test_no_classes_fails_v8(db, minimal_school):
    """A school without active classes should fail V8."""
    for c in minimal_school["classes"]:
        c.is_active = False
    db.commit()
    result = validate_school(minimal_school["school"].id, db)
    assert not result.is_valid
    assert any(e.rule == "V8" for e in result.errors)

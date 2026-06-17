"""
Solver correctness tests.

Each test calls _solve() directly (not via the background-task wrapper) so it
runs synchronously in the same DB session as the test fixture.
"""
from collections import defaultdict

import pytest

from app.services.solver import _solve
from app.models.schedule import ScheduleEntry, ScheduleStatus


def _run(db, minimal_school) -> list[ScheduleEntry]:
    """Helper: run solver and return the generated entries."""
    _solve(minimal_school["schedule"].id, db)
    db.refresh(minimal_school["schedule"])
    return db.query(ScheduleEntry).filter_by(schedule_id=minimal_school["schedule"].id).all()


def test_solver_completes(db, minimal_school):
    """Solver must finish with COMPLETE status, not FAILED."""
    _run(db, minimal_school)
    assert minimal_school["schedule"].status == ScheduleStatus.COMPLETE


def test_correct_total_lesson_count(db, minimal_school):
    """Total entries = sum of hours_per_week across all assignments (4 × 2 = 8)."""
    entries = _run(db, minimal_school)
    expected = sum(a.hours_per_week for a in minimal_school["assignments"])
    assert len(entries) == expected


def test_each_assignment_has_correct_entry_count(db, minimal_school):
    """Each assignment should have exactly hours_per_week entries."""
    entries = _run(db, minimal_school)
    counts: dict[int, int] = defaultdict(int)
    for e in entries:
        counts[e.assignment_id] += 1
    for a in minimal_school["assignments"]:
        assert counts[a.id] == a.hours_per_week, (
            f"Assignment {a.id} expected {a.hours_per_week} entries, got {counts[a.id]}"
        )


def test_no_room_double_booking(db, minimal_school):
    """No two entries may share the same (time_slot, room) pair."""
    entries = _run(db, minimal_school)
    pairs = [(e.time_slot_id, e.room_id) for e in entries]
    assert len(pairs) == len(set(pairs)), "Room double-booking detected"


def test_no_teacher_double_booking(db, minimal_school):
    """No teacher may appear in two entries at the same time slot."""
    entries = _run(db, minimal_school)
    teacher_map = {a.id: a.teacher_id for a in minimal_school["assignments"]}
    pairs = [(e.time_slot_id, teacher_map[e.assignment_id]) for e in entries]
    assert len(pairs) == len(set(pairs)), "Teacher double-booking detected"


def test_no_class_double_booking(db, minimal_school):
    """No class may have two lessons at the same time slot."""
    entries = _run(db, minimal_school)
    class_map = {a.id: a.student_class_id for a in minimal_school["assignments"]}
    pairs = [(e.time_slot_id, class_map[e.assignment_id]) for e in entries]
    assert len(pairs) == len(set(pairs)), "Class double-booking detected"


def test_entries_use_valid_slots(db, minimal_school):
    """All time_slot_id values in entries must belong to this school's slot set."""
    entries = _run(db, minimal_school)
    valid_slot_ids = {s.id for s in minimal_school["slots"]}
    for e in entries:
        assert e.time_slot_id in valid_slot_ids, f"Entry uses unknown slot {e.time_slot_id}"


def test_entries_use_valid_rooms(db, minimal_school):
    """All room_id values in entries must belong to this school's room set."""
    entries = _run(db, minimal_school)
    valid_room_ids = {r.id for r in minimal_school["rooms"]}
    for e in entries:
        assert e.room_id in valid_room_ids, f"Entry uses unknown room {e.room_id}"


def test_home_room_lessons_use_home_room(db, minimal_school):
    """Ordinary (non-special) lessons of a class with a home room land in that room."""
    home = minimal_school["rooms"][0]
    cls = minimal_school["classes"][0]
    cls.home_room_id = home.id
    db.commit()

    entries = _run(db, minimal_school)
    class_map = {a.id: a.student_class_id for a in minimal_school["assignments"]}
    cls_entries = [e for e in entries if class_map[e.assignment_id] == cls.id]
    assert cls_entries, "expected entries for the class"
    # Subjects in the fixture are not special-room, so all should be in the home room
    assert all(e.room_id == home.id for e in cls_entries), (
        "ordinary lessons of a home-room class must use the home room"
    )


def test_preferred_room_honoured(db, minimal_school):
    """When a preferred room is set, the solver should use it for all or most lessons."""
    preferred_room = minimal_school["rooms"][0]
    a = minimal_school["assignments"][0]
    a.preferred_room_id = preferred_room.id
    db.commit()

    entries = _run(db, minimal_school)
    a_entries = [e for e in entries if e.assignment_id == a.id]
    assert all(e.room_id == preferred_room.id for e in a_entries), (
        "All lessons of an assignment with a preferred room should use that room when possible"
    )

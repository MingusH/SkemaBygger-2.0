"""
Shared pytest fixtures for solver and validation tests.

Requires the Docker stack to be running (docker compose up).
Tests connect to the DB forwarded at localhost:5432 and clean up after themselves.

Run:
    docker compose exec backend pytest tests/ -v
  or (from backend/ with DB accessible at localhost):
    pytest tests/ -v
"""
import pytest
from datetime import time

from app.database import SessionLocal
from app.models.school import School
from app.models.timeslot import TimeSlot
from app.models.room import Room, RoomType
from app.models.subject import Subject, SubjectCategory
from app.models.teacher import Teacher, TeacherSubject
from app.models.student_class import StudentClass
from app.models.assignment import Assignment
from app.models.schedule import Schedule, ScheduleStatus


@pytest.fixture()
def db():
    """Open a DB session. Each test commits its own data and cleans up via CASCADE delete."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def minimal_school(db):
    """
    A minimal but fully valid school for solver and validation tests:
      - 1 school  (7 periods × 5 days = 35 slots)
      - 35 time slots
      - 2 rooms
      - 2 subjects  (Dansk, Matematik)
      - 1 teacher   (qualified for both)
      - 2 classes   (1A, 2A)
      - 4 assignments  (each class × each subject, 2 hrs/week → 8 total lessons)
      - 1 Schedule  (DRAFT)
    """
    school = School(
        name="Test Skole",
        short_name="TEST",
        academic_year="2026/2027",
        periods_per_day=7,
        days_per_week=5,
    )
    db.add(school)
    db.flush()

    # 35 time slots: 5 days × 7 periods, each 45 min starting 08:00
    slots: list[TimeSlot] = []
    for day in range(1, 6):
        for period in range(1, 8):
            hour = 7 + period  # period 1 → 08:xx, period 7 → 14:xx
            slot = TimeSlot(
                school_id=school.id,
                day_of_week=day,
                period_number=period,
                start_time=time(hour, 0),
                end_time=time(hour, 45),
            )
            db.add(slot)
            slots.append(slot)
    db.flush()

    room1 = Room(school_id=school.id, name="Lokale 1", short_code="L1", capacity=30, room_type=RoomType.STANDARD)
    room2 = Room(school_id=school.id, name="Lokale 2", short_code="L2", capacity=30, room_type=RoomType.STANDARD)
    db.add_all([room1, room2])
    db.flush()

    subj_dansk = Subject(
        school_id=school.id, name="Dansk", short_code="DA",
        category=SubjectCategory.HUMANISTISK,
        requires_special_room=False, is_elective_slot=False,
    )
    subj_mat = Subject(
        school_id=school.id, name="Matematik", short_code="MA",
        category=SubjectCategory.NATURFAG,
        requires_special_room=False, is_elective_slot=False,
    )
    db.add_all([subj_dansk, subj_mat])
    db.flush()

    teacher = Teacher(
        school_id=school.id,
        first_name="Test", last_name="Lærer",
        short_code="TL",
    )
    db.add(teacher)
    db.flush()

    db.add(TeacherSubject(teacher_id=teacher.id, subject_id=subj_dansk.id))
    db.add(TeacherSubject(teacher_id=teacher.id, subject_id=subj_mat.id))
    db.flush()

    class_1a = StudentClass(school_id=school.id, name="1A", grade_level=1, student_count=25)
    class_2a = StudentClass(school_id=school.id, name="2A", grade_level=2, student_count=25)
    db.add_all([class_1a, class_2a])
    db.flush()

    assignments: list[Assignment] = []
    for cls in [class_1a, class_2a]:
        for subj in [subj_dansk, subj_mat]:
            a = Assignment(
                school_id=school.id,
                teacher_id=teacher.id,
                subject_id=subj.id,
                student_class_id=cls.id,
                hours_per_week=2,
                academic_year="2026/2027",
            )
            db.add(a)
            assignments.append(a)
    db.flush()

    schedule = Schedule(
        school_id=school.id,
        name="Test Skema",
        academic_year="2026/2027",
        status=ScheduleStatus.DRAFT,
    )
    db.add(schedule)
    db.commit()

    yield {
        "school": school,
        "slots": slots,
        "rooms": [room1, room2],
        "subjects": [subj_dansk, subj_mat],
        "teacher": teacher,
        "classes": [class_1a, class_2a],
        "assignments": assignments,
        "schedule": schedule,
    }

    # Cleanup — CASCADE deletes all child rows when the school is deleted
    db.refresh(school)
    db.delete(school)
    db.commit()

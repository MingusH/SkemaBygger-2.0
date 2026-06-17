"""
Pre-flight validation rules V1-V8 (blockers) and W1-W5 (warnings).
All rules operate on a single school's data.
"""
from sqlalchemy.orm import Session
from app.models.assignment import Assignment
from app.models.school import School
from app.models.teacher import Teacher, TeacherSubject
from app.models.student_class import StudentClass
from app.models.room import Room
from app.models.timeslot import TimeSlot
from app.models.constraints import TeacherUnavailability, ConstraintType
from app.models.subject import Subject
from app.schemas.validation import ValidationResult, ValidationIssue


def validate_school(school_id: int, db: Session) -> ValidationResult:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    def err(rule: str, msg: str, etype: str | None = None, eid: int | None = None):
        errors.append(ValidationIssue(rule=rule, level="error", message=msg, entity_type=etype, entity_id=eid))

    def warn(rule: str, msg: str, etype: str | None = None, eid: int | None = None):
        warnings.append(ValidationIssue(rule=rule, level="warning", message=msg, entity_type=etype, entity_id=eid))

    school = db.get(School, school_id)
    if not school:
        err("V0", "School not found")
        return ValidationResult(school_id=school_id, is_valid=False, errors=errors)

    teachers = db.query(Teacher).filter(Teacher.school_id == school_id, Teacher.is_active == True).all()
    classes = db.query(StudentClass).filter(StudentClass.school_id == school_id, StudentClass.is_active == True).all()
    subjects = db.query(Subject).filter(Subject.school_id == school_id).all()
    rooms = db.query(Room).filter(Room.school_id == school_id, Room.is_active == True).all()
    assignments = db.query(Assignment).filter(Assignment.school_id == school_id).all()
    slots = db.query(TimeSlot).filter(TimeSlot.school_id == school_id).all()

    # V8 — minimum entities
    if not classes:
        err("V8", "No active classes defined")
    if not teachers:
        err("V8", "No active teachers defined")
    if not subjects:
        err("V8", "No subjects seeded — run POST /schools/{id}/seed-subjects first")
    if not rooms:
        err("V8", "No active rooms defined")

    # V6 — time slot grid completeness
    expected_slots = school.periods_per_day * school.days_per_week
    if len(slots) != expected_slots:
        err("V6", f"Expected {expected_slots} time slots ({school.days_per_week} days × {school.periods_per_day} periods) but found {len(slots)}")

    if not assignments:
        warn("V7", "No assignments defined — nothing to schedule")
        return ValidationResult(school_id=school_id, is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    # V7 — no zero-hour assignments
    for a in assignments:
        if a.hours_per_week <= 0:
            err("V7", f"Assignment {a.id} has hours_per_week={a.hours_per_week}", "assignment", a.id)

    # Build lookup sets
    teacher_ids = {t.id for t in teachers}
    class_ids = {c.id for c in classes}
    subject_ids = {s.id for s in subjects}
    qualifications = {(ts.teacher_id, ts.subject_id) for ts in db.query(TeacherSubject).all()}

    for a in assignments:
        # V1 — all referenced entities are active
        if a.teacher_id not in teacher_ids:
            err("V1", f"Assignment {a.id}: teacher {a.teacher_id} is inactive or missing", "assignment", a.id)
        if a.student_class_id not in class_ids:
            err("V1", f"Assignment {a.id}: class {a.student_class_id} is inactive or missing", "assignment", a.id)
        if a.subject_id not in subject_ids:
            err("V1", f"Assignment {a.id}: subject {a.subject_id} missing", "assignment", a.id)

        # V2 — teacher is qualified
        if (a.teacher_id, a.subject_id) not in qualifications:
            err("V2", f"Assignment {a.id}: teacher {a.teacher_id} has no qualification for subject {a.subject_id}", "assignment", a.id)

        # W5 — consecutive flag but 1 hour/week
        if a.requires_consecutive and a.hours_per_week == 1:
            warn("W5", f"Assignment {a.id}: requires_consecutive=True but hours_per_week=1 (contradiction)", "assignment", a.id)

    # V3 — total hours per class ≤ available slots
    available_slots = school.periods_per_day * school.days_per_week
    from collections import defaultdict
    class_hours: dict[int, int] = defaultdict(int)
    for a in assignments:
        class_hours[a.student_class_id] += a.hours_per_week
    for class_id, total in class_hours.items():
        if total > available_slots:
            err("V3", f"Class {class_id}: {total} total hours/week exceeds {available_slots} available slots", "class", class_id)

    # ── Room model: home rooms + typed special-room pool ──────────────────────
    special_subject_ids = {s.id for s in subjects if s.requires_special_room}
    subject_required_type = {s.id: s.required_room_type for s in subjects}
    active_room_ids = {r.id for r in rooms}
    home_room_of_class = {
        c.id: c.home_room_id
        for c in classes
        if c.home_room_id is not None and c.home_room_id in active_room_ids
    }
    home_room_ids = set(home_room_of_class.values())

    # Pinned rooms (explicit preferred_room_id, not a home room) are reserved.
    pinned_room_of_assignment = {
        a.id: a.preferred_room_id
        for a in assignments
        if a.preferred_room_id is not None
        and a.preferred_room_id in active_room_ids
        and a.preferred_room_id not in home_room_ids
    }
    pinned_room_ids = set(pinned_room_of_assignment.values())

    pool_rooms = [r for r in rooms if r.id not in home_room_ids and r.id not in pinned_room_ids]
    required_types = {t for t in subject_required_type.values() if t is not None}

    rooms_of_type: dict[object, int] = defaultdict(int)
    for r in pool_rooms:
        rooms_of_type[r.room_type] += 1

    # V9 — pinned-room capacity: each pinned room holds one lesson per slot
    pinned_lessons_per_room: dict[int, int] = defaultdict(int)
    for a in assignments:
        if a.id in pinned_room_of_assignment:
            pinned_lessons_per_room[pinned_room_of_assignment[a.id]] += a.hours_per_week
    for rid, total in pinned_lessons_per_room.items():
        if total > available_slots:
            err("V9", f"{total} weekly lessons are pinned to one room but only {available_slots} slots exist; spread them across rooms or reduce hours", "room", rid)

    # V5 — every required room type must have at least one room of that type
    for rtype in required_types:
        total_of_type = sum(1 for r in rooms if r.room_type == rtype)
        if total_of_type == 0:
            err("V5", f"A subject requires a {rtype.value} room but the school has no room of that type", None, None)

    # V9 — capacity per room bucket (typed pools + general pool)
    typed_lessons: dict[object, int] = defaultdict(int)
    general_lessons = 0
    classes_without_home: set[int] = set()
    for a in assignments:
        if a.id in pinned_room_of_assignment:
            continue  # counted in the pinned-room capacity check above
        has_home = a.student_class_id in home_room_of_class
        if not has_home:
            classes_without_home.add(a.student_class_id)
        is_special = a.subject_id in special_subject_ids
        if not (is_special or not has_home):
            continue  # ordinary home-room lesson — no pool needed
        rtype = subject_required_type.get(a.subject_id)
        if rtype is not None:
            typed_lessons[rtype] += a.hours_per_week
        else:
            general_lessons += a.hours_per_week

    for rtype, total in typed_lessons.items():
        cap = available_slots * rooms_of_type.get(rtype, 0)
        if total > cap:
            err(
                "V9",
                f"{total} weekly {rtype.value} lessons exceed capacity of {cap} "
                f"({available_slots} slots × {rooms_of_type.get(rtype, 0)} {rtype.value} rooms). Add more {rtype.value} rooms.",
            )

    general_rooms = sum(1 for r in pool_rooms if r.room_type not in required_types)
    general_capacity = available_slots * general_rooms
    if general_lessons > general_capacity:
        err(
            "V9",
            f"{general_lessons} weekly lessons need a general shared room but capacity is only {general_capacity} "
            f"({available_slots} slots × {general_rooms} non-home rooms). Give classes home rooms (stamlokaler) or add rooms.",
        )

    # W6 — classes without a home room fall back to the shared room pool
    for cid in classes_without_home:
        warn("W6", f"Class {cid} has no home room (stamlokale); its ordinary lessons compete for shared rooms", "class", cid)

    # V4 — total hours per teacher ≤ available slots minus hard unavailabilities
    teacher_hours: dict[int, int] = defaultdict(int)
    for a in assignments:
        teacher_hours[a.teacher_id] += a.hours_per_week
    for teacher in teachers:
        hard_unavail = db.query(TeacherUnavailability).filter(
            TeacherUnavailability.teacher_id == teacher.id,
            TeacherUnavailability.constraint_type == ConstraintType.HARD,
        ).count()
        cap = available_slots - hard_unavail
        used = teacher_hours.get(teacher.id, 0)
        if used > cap:
            err("V4", f"Teacher {teacher.id}: {used} assignment hours exceeds capacity of {cap} (slots={available_slots}, hard_unavail={hard_unavail})", "teacher", teacher.id)
        # W1 — exceeds soft max
        if teacher.max_hours_per_week and used > teacher.max_hours_per_week:
            warn("W3", f"Teacher {teacher.id}: {used} hours exceeds max_hours_per_week={teacher.max_hours_per_week}", "teacher", teacher.id)

    # V5 — special-room subjects have a matching room
    special_subjects = {s.id for s in subjects if s.requires_special_room}
    if special_subjects:
        for a in assignments:
            if a.subject_id in special_subjects and a.preferred_room_id is None:
                warn("W1", f"Assignment {a.id}: subject requires a special room but no preferred_room_id is set", "assignment", a.id)

    return ValidationResult(
        school_id=school_id,
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )

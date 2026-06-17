from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.assignment import Assignment
from app.models.elective import ElectiveBand
from app.models.timeslot import TimeSlot
from app.services.timecalc import clock_hours_per_period, LESSON_TO_CLOCK
from app.models.school import School
from app.models.student_class import StudentClass
from app.models.subject import Subject, MinistryHours
from app.models.grade_minimums import GradeMinimumHours
from app.models.teacher import Teacher, TeacherSubject
from app.schemas.assignment import AssignmentCreate, AssignmentUpdate, AssignmentRead
from app.routers._deps import require_school_admin, require_school_member

router = APIRouter(prefix="/schools/{school_id}/assignments", tags=["assignments"])


@router.get("", response_model=list[AssignmentRead])
def list_assignments(
    school_id: int,
    class_id: int | None = None,
    teacher_id: int | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_school_member),
):
    q = db.query(Assignment).filter(Assignment.school_id == school_id)
    if class_id:
        q = q.filter(Assignment.student_class_id == class_id)
    if teacher_id:
        q = q.filter(Assignment.teacher_id == teacher_id)
    return q.all()


@router.post("", response_model=AssignmentRead, status_code=201)
def create_assignment(school_id: int, body: AssignmentCreate, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    a = Assignment(school_id=school_id, **body.model_dump())
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


@router.get("/{assignment_id}", response_model=AssignmentRead)
def get_assignment(school_id: int, assignment_id: int, db: Session = Depends(get_db), _=Depends(require_school_member)):
    a = db.query(Assignment).filter(Assignment.id == assignment_id, Assignment.school_id == school_id).first()
    if not a:
        raise HTTPException(404, "Assignment not found")
    return a


@router.patch("/{assignment_id}", response_model=AssignmentRead)
def update_assignment(school_id: int, assignment_id: int, body: AssignmentUpdate, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    a = db.query(Assignment).filter(Assignment.id == assignment_id, Assignment.school_id == school_id).first()
    if not a:
        raise HTTPException(404, "Assignment not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(a, k, v)
    db.commit()
    db.refresh(a)
    return a


@router.delete("/{assignment_id}", status_code=204)
def delete_assignment(school_id: int, assignment_id: int, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    a = db.query(Assignment).filter(Assignment.id == assignment_id, Assignment.school_id == school_id).first()
    if not a:
        raise HTTPException(404, "Assignment not found")
    db.delete(a)
    db.commit()


@router.post("/bulk-auto-assign")
def bulk_auto_assign(school_id: int, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    """Clear all existing assignments and re-assign every mandatory UVM subject to every class
    using load-balanced teacher selection across the full teacher pool."""
    school = db.get(School, school_id)
    if not school:
        raise HTTPException(404, "School not found")

    classes = db.query(StudentClass).filter(StudentClass.school_id == school_id, StudentClass.is_active == True).all()
    subjects = db.query(Subject).filter(Subject.school_id == school_id, Subject.is_elective_slot == False).all()
    teachers = db.query(Teacher).filter(Teacher.school_id == school_id, Teacher.is_active == True).all()

    # subject_id → grade → hours_per_week (ministry minimum)
    ministry: dict[int, dict[int, float]] = {s.id: {} for s in subjects}
    for mh in db.query(MinistryHours).filter(MinistryHours.subject_id.in_([s.id for s in subjects])).all():
        ministry[mh.subject_id][mh.grade] = mh.hours_per_week

    # UVM curriculum subjects have a ministry minimum; this routine owns (and rebuilds)
    # their assignments. Custom subjects like "Klassens tid" have none — their manual
    # assignments are preserved untouched.
    uvm_subject_ids = {sid for sid, m in ministry.items() if m}
    if uvm_subject_ids:
        db.query(Assignment).filter(
            Assignment.school_id == school_id,
            Assignment.subject_id.in_(uvm_subject_ids),
        ).delete(synchronize_session=False)

    # subject_id → set of qualified teacher_ids
    qual: dict[int, set[int]] = {s.id: set() for s in subjects}
    for ts in db.query(TeacherSubject).filter(TeacherSubject.teacher_id.in_([t.id for t in teachers])).all():
        if ts.subject_id in qual:
            qual[ts.subject_id].add(ts.teacher_id)

    # grade → total_annual (weekly-lesson-equivalent of the ministry yearly total).
    grade_totals: dict[int, float] = {g.grade: g.total_annual for g in db.query(GradeMinimumHours).all()}

    # The ministry yearly total is real clock time INCLUDING breaks; a scheduled period
    # occupies period_clock hours (lesson + following break). Convert the total into the
    # number of periods the week must hold so the delivered school-day time hits the total.
    slots = db.query(TimeSlot).filter(TimeSlot.school_id == school_id).all()
    period_clock = clock_hours_per_period(slots)

    # grade → weekly hours delivered by elective bands (scheduled outside assignments).
    band_hours_by_grade: dict[int, int] = defaultdict(int)
    for b in db.query(ElectiveBand).filter(ElectiveBand.school_id == school_id).all():
        band_hours_by_grade[b.grade_level] += b.hours_per_week

    # Subjects ranked by priority for distributing the surplus above the minimum.
    ranked_subjects = sorted(subjects, key=lambda s: (s.priority, s.name))

    def target_periods_for_grade(grade: int, sum_min: int) -> int:
        """How many periods/week the grade should hold to deliver its yearly total
        (incl. breaks): total_annual is in 0.75-clock lesson units, so scale by
        LESSON_TO_CLOCK / period_clock to convert to real break-inclusive periods."""
        total = grade_totals.get(grade)
        if total is None:
            return sum_min
        return round(total * LESSON_TO_CLOCK / period_clock)

    def hours_for_grade(grade: int) -> dict[int, int]:
        """Per-subject lesson count for a grade: ministry minimum + surplus distributed
        round-robin by priority until the grade total is reached. Elective-band hours
        are delivered separately, so subtract them from the assignment target."""
        base = {s.id: round(ministry.get(s.id, {}).get(grade, 0.0)) for s in subjects}
        base = {sid: h for sid, h in base.items() if h > 0}
        sum_min = sum(base.values())
        target = target_periods_for_grade(grade, sum_min) - band_hours_by_grade.get(grade, 0)
        surplus = max(0, target - sum_min)

        # Only boost subjects already taught at this grade (have a ministry minimum) AND
        # flagged add_extra — excluded subjects (e.g. Idræt) stay at their minimum so a
        # double-lesson subject never ends up with an odd, lone single period.
        eligible = [s for s in ranked_subjects if s.id in base and s.add_extra]
        i = 0
        while surplus > 0 and eligible:
            base[eligible[i % len(eligible)].id] += 1
            surplus -= 1
            i += 1
        return base

    # Precompute per-grade hour maps (one per distinct grade present)
    grade_hours: dict[int, dict[int, int]] = {
        grade: hours_for_grade(grade) for grade in {c.grade_level for c in classes}
    }

    # Seed running load from any preserved (custom-subject) assignments so load
    # balancing still accounts for hours already on a teacher.
    load: dict[int, int] = {t.id: 0 for t in teachers}
    for a in db.query(Assignment).filter(Assignment.school_id == school_id).all():
        if a.teacher_id in load:
            load[a.teacher_id] += a.hours_per_week

    created = 0
    skipped_no_teacher = 0

    for cls in classes:
        for subj_id, hours_int in grade_hours[cls.grade_level].items():
            if hours_int <= 0:
                continue

            qualified = [t for t in teachers if t.id in qual.get(subj_id, set())]
            if not qualified:
                skipped_no_teacher += 1
                continue

            best = min(qualified, key=lambda t: load[t.id])

            db.add(Assignment(
                school_id=school_id,
                teacher_id=best.id,
                subject_id=subj_id,
                student_class_id=cls.id,
                hours_per_week=hours_int,
                academic_year=school.academic_year,
                requires_consecutive=False,
            ))
            load[best.id] += hours_int
            created += 1

    db.commit()

    # Per-grade check: does the scheduled school-day time (subjects + bands, incl.
    # breaks) reach the ministry yearly total? A grade falls short only when a needed
    # subject has no qualified teacher.
    grade_check = []
    for grade in sorted(grade_hours):
        hmap = grade_hours[grade]
        bands = band_hours_by_grade.get(grade, 0)
        target_periods = sum(hmap.values()) + bands
        achieved_periods = sum(h for sid, h in hmap.items() if qual.get(sid)) + bands
        grade_check.append({
            "grade": grade,
            "target_periods": target_periods,
            "achieved_periods": achieved_periods,
            "target_clock_hours": round(target_periods * period_clock * school.weeks_per_year),
            "delivered_clock_hours": round(achieved_periods * period_clock * school.weeks_per_year),
            "meets_total": achieved_periods >= target_periods,
        })

    return {"created": created, "skipped_no_teacher": skipped_no_teacher, "grade_totals": grade_check}

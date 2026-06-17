from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.school import School
from app.models.special_event import SpecialEvent, EventScope
from app.models.student_class import StudentClass
from app.models.grade_minimums import GradeMinimumHours
from app.models.schedule import Schedule, ScheduleEntry, ScheduleStatus
from app.models.elective import ElectiveOffering
from app.schemas.special_event import (
    SpecialEventCreate, SpecialEventUpdate, SpecialEventRead,
    ClassTimeBankEntry, SchoolTimeBankRead,
)
from app.services.timecalc import clock_hours_from_slots, LESSON_TO_CLOCK, STANDARD_WEEKS
from app.routers._deps import require_school_member, require_school_admin

router = APIRouter(prefix="/schools/{school_id}/special-events", tags=["special-events"])


def _event_clock_hours(event: SpecialEvent, day_hours: dict[int, float]) -> float:
    """Clock hours a class loses to an event: for every Mon–Fri date the event spans,
    the hours that class normally has that weekday, minus any partial teaching that
    still happens during the whole event (hours_override). `day_hours` maps
    day_of_week (1=Mon..5=Fri) → the class's real clock hours that weekday."""
    normal = 0.0
    d = event.start_date
    while d <= event.end_date:
        dow = d.weekday() + 1  # Mon=1 .. Sun=7
        if dow <= 5:
            normal += day_hours.get(dow, 0.0)
        d += timedelta(days=1)
    return max(0.0, normal - (event.hours_override or 0.0))


def _event_read(event: SpecialEvent) -> SpecialEventRead:
    return SpecialEventRead.from_orm_with_classes(event)


@router.get("", response_model=list[SpecialEventRead])
def list_events(school_id: int, db: Session = Depends(get_db), _=Depends(require_school_member)):
    events = (
        db.query(SpecialEvent)
        .filter(SpecialEvent.school_id == school_id)
        .order_by(SpecialEvent.start_date)
        .all()
    )
    return [_event_read(e) for e in events]


@router.post("", response_model=SpecialEventRead, status_code=201)
def create_event(
    school_id: int,
    body: SpecialEventCreate,
    db: Session = Depends(get_db),
    _=Depends(require_school_admin),
):
    school = db.get(School, school_id)
    if not school:
        raise HTTPException(404, "School not found")
    if body.end_date < body.start_date:
        raise HTTPException(422, "end_date must be >= start_date")

    event = SpecialEvent(
        school_id=school_id,
        name=body.name,
        event_type=body.event_type,
        scope=body.scope,
        start_date=body.start_date,
        end_date=body.end_date,
        hours_override=body.hours_override,
        description=body.description,
    )
    if body.scope == EventScope.PER_CLASS and body.class_ids:
        classes = db.query(StudentClass).filter(
            StudentClass.id.in_(body.class_ids),
            StudentClass.school_id == school_id,
        ).all()
        event.classes = classes

    db.add(event)
    db.commit()
    db.refresh(event)
    return _event_read(event)


@router.patch("/{event_id}", response_model=SpecialEventRead)
def update_event(
    school_id: int,
    event_id: int,
    body: SpecialEventUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_school_admin),
):
    event = db.query(SpecialEvent).filter(
        SpecialEvent.id == event_id, SpecialEvent.school_id == school_id
    ).first()
    if not event:
        raise HTTPException(404, "Event not found")

    update_data = body.model_dump(exclude_none=True)
    class_ids = update_data.pop("class_ids", None)

    for k, v in update_data.items():
        setattr(event, k, v)

    if class_ids is not None:
        if event.scope == EventScope.PER_CLASS:
            classes = db.query(StudentClass).filter(
                StudentClass.id.in_(class_ids),
                StudentClass.school_id == school_id,
            ).all()
            event.classes = classes
        else:
            event.classes = []

    db.commit()
    db.refresh(event)
    return _event_read(event)


@router.delete("/{event_id}", status_code=204)
def delete_event(
    school_id: int,
    event_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_school_admin),
):
    event = db.query(SpecialEvent).filter(
        SpecialEvent.id == event_id, SpecialEvent.school_id == school_id
    ).first()
    if not event:
        raise HTTPException(404, "Event not found")
    db.delete(event)
    db.commit()


# --- Time bank (read-only calculation) ---

time_bank_router = APIRouter(prefix="/schools/{school_id}", tags=["special-events"])


def _pick_schedule(db: Session, school_id: int, schedule_id: int | None) -> Schedule | None:
    """Resolve which schedule to base the timebank on. Explicit id wins (must belong
    to the school); otherwise the most recent schedule that actually has entries,
    preferring PUBLISHED/COMPLETE."""
    if schedule_id is not None:
        sched = db.query(Schedule).filter(
            Schedule.id == schedule_id, Schedule.school_id == school_id
        ).first()
        if not sched:
            raise HTTPException(404, "Schedule not found")
        return sched

    sched_ids_with_entries = {
        row[0] for row in db.query(ScheduleEntry.schedule_id)
        .join(Schedule, Schedule.id == ScheduleEntry.schedule_id)
        .filter(Schedule.school_id == school_id)
        .distinct()
    }
    if not sched_ids_with_entries:
        return None
    candidates = db.query(Schedule).filter(
        Schedule.school_id == school_id, Schedule.id.in_(sched_ids_with_entries)
    ).all()

    def sort_key(s: Schedule):
        preferred = 0 if s.status in (ScheduleStatus.PUBLISHED, ScheduleStatus.COMPLETE) else 1
        when = s.generated_at.timestamp() if s.generated_at else 0.0
        return (preferred, -when, -s.id)

    return sorted(candidates, key=sort_key)[0]


@time_bank_router.get("/time-bank", response_model=SchoolTimeBankRead)
def get_time_bank(
    school_id: int,
    schedule_id: int | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_school_member),
):
    school = db.get(School, school_id)
    if not school:
        raise HTTPException(404, "School not found")

    classes = db.query(StudentClass).filter(
        StudentClass.school_id == school_id, StudentClass.is_active == True
    ).order_by(StudentClass.grade_level, StudentClass.name).all()

    schedule = _pick_schedule(db, school_id, schedule_id)

    # Load the chosen schedule's entries with everything needed to attribute each
    # placed lesson to a class (regular → assignment.student_class; band → grade).
    sched_entries: list[ScheduleEntry] = []
    if schedule is not None:
        sched_entries = (
            db.query(ScheduleEntry)
            .filter(ScheduleEntry.schedule_id == schedule.id)
            .options(
                joinedload(ScheduleEntry.time_slot),
                joinedload(ScheduleEntry.assignment),
                joinedload(ScheduleEntry.elective_offering).joinedload(ElectiveOffering.band),
            )
            .all()
        )

    if not sched_entries:
        return SchoolTimeBankRead(
            school_id=school_id,
            weeks_per_year=school.weeks_per_year,
            schedule_id=schedule.id if schedule else None,
            has_schedule=False,
            entries=[],
        )

    # Map each placed lesson to the timeslots a class actually attends. A regular
    # entry belongs to one class; an elective-band offering puts the whole grade in
    # that slot. Dedupe per class by time_slot id (parallel band offerings share a slot).
    active_by_grade: dict[int, list[StudentClass]] = {}
    for c in classes:
        active_by_grade.setdefault(c.grade_level, []).append(c)

    class_slots: dict[int, dict[int, object]] = {c.id: {} for c in classes}
    # Distinct timeslots of timebank-drawing bands, per grade — these net back out.
    draw_slots_by_grade: dict[int, dict[int, object]] = {}

    for e in sched_entries:
        ts = e.time_slot
        if e.assignment_id is not None and e.assignment is not None:
            cid = e.assignment.student_class_id
            if cid in class_slots:
                class_slots[cid][ts.id] = ts
        elif e.elective_offering is not None:
            band = e.elective_offering.band
            for c in active_by_grade.get(band.grade_level, []):
                class_slots[c.id][ts.id] = ts
            if band.draws_timebank:
                draw_slots_by_grade.setdefault(band.grade_level, {})[ts.id] = ts

    events = db.query(SpecialEvent).filter(SpecialEvent.school_id == school_id).all()
    grade_mins = {g.grade: g for g in db.query(GradeMinimumHours).all()}

    entries: list[ClassTimeBankEntry] = []
    for cls in classes:
        weekly_hours, day_hours = clock_hours_from_slots(class_slots[cls.id].values())
        delivered_base = weekly_hours * school.weeks_per_year

        # Events affecting this class draw hours from the bank, based on the hours the
        # class really has on each affected weekday.
        affecting = [
            e for e in events
            if e.scope == EventScope.SCHOOL_WIDE
            or cls.id in {c.id for c in e.classes}
        ]
        timebank_used = sum(_event_clock_hours(e, day_hours) for e in affecting)

        # Timebank-drawing bands (e.g. 2nd practical) are physically delivered but net
        # back toward the minimum, so they also spend the bank.
        draw_slots = draw_slots_by_grade.get(cls.grade_level)
        if draw_slots:
            draw_weekly, _dh = clock_hours_from_slots(draw_slots.values())
            timebank_used += draw_weekly * school.weeks_per_year

        delivered = delivered_base - timebank_used

        gmin = grade_mins.get(cls.grade_level)
        if gmin:
            # Ministry figures are stored as weekly 45-min lessons; ×40×0.75 recovers
            # the PDF's original yearly 60-min totals (which already include breaks).
            ministry_min = gmin.annual_minimum * STANDARD_WEEKS * LESSON_TO_CLOCK
            timebank_pool = gmin.timebank_hours * STANDARD_WEEKS * LESSON_TO_CLOCK
        else:
            ministry_min = 0.0
            timebank_pool = 0.0

        entries.append(ClassTimeBankEntry(
            class_id=cls.id,
            class_name=cls.name,
            grade_level=cls.grade_level,
            weekly_hours=round(weekly_hours, 2),
            delivered=round(delivered, 1),
            ministry_min_hours=round(ministry_min, 1),
            timebank_pool=round(timebank_pool, 1),
            timebank_used=round(timebank_used, 1),
            balance=round(delivered - ministry_min, 1),
            is_sufficient=delivered >= ministry_min,
        ))

    return SchoolTimeBankRead(
        school_id=school_id,
        weeks_per_year=school.weeks_per_year,
        schedule_id=schedule.id,
        has_schedule=True,
        entries=entries,
    )

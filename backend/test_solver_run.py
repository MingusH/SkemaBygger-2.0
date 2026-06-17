"""Ad-hoc verification: run the solver for each school and check
1) earliness, 2) same-day duplicates adjacent, 3) no double bookings."""
import os
from collections import defaultdict
from app.database import SessionLocal
from app.models.schedule import Schedule, ScheduleEntry, ScheduleStatus
from app.models.assignment import Assignment
from app.models.timeslot import TimeSlot
from app.services.solver import run_solver

db = SessionLocal()
school_ids = [sid for (sid,) in db.query(Schedule.school_id).distinct()]
if os.environ.get("ONLY_SCHOOL"):
    school_ids = [int(os.environ["ONLY_SCHOOL"])]

for school_id in sorted(school_ids):
    sched = Schedule(school_id=school_id, name=f"solver-test school {school_id}", academic_year="2026/2027", status=ScheduleStatus.GENERATING)
    db.add(sched)
    db.commit()
    sid = sched.id

    run_solver(sid)
    db.expire_all()
    sched = db.get(Schedule, sid)
    print(f"\n=== school {school_id} (schedule {sid}): {sched.status} ===")
    print("params:", sched.algorithm_params)
    if sched.status != ScheduleStatus.COMPLETE:
        continue

    rows = (
        db.query(ScheduleEntry, Assignment, TimeSlot)
        .join(Assignment, ScheduleEntry.assignment_id == Assignment.id)
        .join(TimeSlot, ScheduleEntry.time_slot_id == TimeSlot.id)
        .filter(ScheduleEntry.schedule_id == sid)
        .all()
    )
    print("entries:", len(rows))

    teacher_slot = defaultdict(int)
    class_slot = defaultdict(int)
    room_slot = defaultdict(int)
    asg_day_periods = defaultdict(list)
    period_count = defaultdict(int)
    for e, a, t in rows:
        teacher_slot[(a.teacher_id, t.id)] += 1
        class_slot[(a.student_class_id, t.id)] += 1
        room_slot[(e.room_id, t.id)] += 1
        asg_day_periods[(a.id, t.day_of_week)].append(t.period_number)
        period_count[t.period_number] += 1

    dbl_t = sum(1 for v in teacher_slot.values() if v > 1)
    dbl_c = sum(1 for v in class_slot.values() if v > 1)
    dbl_r = sum(1 for v in room_slot.values() if v > 1)
    print(f"double-booked teacher/class/room slots: {dbl_t}/{dbl_c}/{dbl_r}")

    non_adjacent = 0
    for (aid, day), periods in asg_day_periods.items():
        ps = sorted(periods)
        if len(ps) >= 2 and (ps[-1] - ps[0] != len(ps) - 1 or len(set(ps)) != len(ps)):
            non_adjacent += 1
            print(f"  NOT ADJACENT: assignment {aid} day {day} periods {ps}")
    multi = sum(1 for v in asg_day_periods.values() if len(v) >= 2)
    print(f"same-day duplicate blocks: {multi}, non-adjacent: {non_adjacent}")
    print("lessons per period:", dict(sorted(period_count.items())))

    # daily cap and 1-2 preference
    over_cap = sum(1 for v in asg_day_periods.values() if len(v) > 4)
    over_pref = sum(1 for v in asg_day_periods.values() if len(v) > 2)
    print(f"assignment-days over hard cap (4): {over_cap}, over preferred (2): {over_pref}")

    # double lessons: requires_consecutive assignments come in same-day pairs,
    # and a 2-block must not span a break longer than 30 minutes
    gap_after = {}  # (day, period) -> minutes until next period starts
    slots_by_day = defaultdict(list)
    for t in db.query(TimeSlot).filter(TimeSlot.school_id == school_id).order_by(TimeSlot.day_of_week, TimeSlot.period_number):
        slots_by_day[t.day_of_week].append(t)
    for day, ts in slots_by_day.items():
        for a, b in zip(ts, ts[1:]):
            gap_after[(day, a.period_number)] = (b.start_time.hour * 60 + b.start_time.minute) - (a.end_time.hour * 60 + a.end_time.minute)

    consec_ids = {a.id: a.hours_per_week for (_, a, _) in rows if a.requires_consecutive}
    bad_pairing = bad_break = 0
    for aid, hours in consec_ids.items():
        day_counts = [len(asg_day_periods.get((aid, d), [])) for d in slots_by_day]
        odd_days = sum(1 for c in day_counts if c % 2 == 1)
        if odd_days > (hours % 2):
            bad_pairing += 1
            print(f"  BAD PAIRING: assignment {aid} ({hours}h) day counts {day_counts}")
        # Any two adjacent occupied periods straddling a >30min break is bad,
        # regardless of how many lessons the assignment has that day.
        for d in slots_by_day:
            ps = sorted(asg_day_periods.get((aid, d), []))
            for p_now, p_nxt in zip(ps, ps[1:]):
                if p_nxt == p_now + 1 and gap_after.get((d, p_now), 0) > 30:
                    bad_break += 1
                    print(f"  BLOCK OVER LONG BREAK: assignment {aid} day {d} periods {ps} (at {p_now}->{p_nxt})")
    print(f"requires_consecutive assignments: {len(consec_ids)}, bad pairing: {bad_pairing}, blocks over long break: {bad_break}")

db.close()

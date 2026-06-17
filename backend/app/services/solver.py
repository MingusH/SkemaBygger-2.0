"""
OR-Tools CP-SAT solver for school schedule generation.

Room model (home-room + typed special rooms):
  - Each class has a *home room* (stamlokale). Ordinary lessons stay there and do
    NOT compete for rooms.
  - Lessons whose subject needs a special room compete for the shared pool of
    non-home rooms. If the subject has a required_room_type (e.g. Idræt -> GYM),
    it may ONLY use pool rooms of that type — a hard constraint.
  - Special lessons without a specific type use the general pool (rooms whose type
    no subject requires). Home-less classes' ordinary lessons also use the general
    pool.

Model (boolean assignment formulation):
  x[lesson, slot] = 1 if the lesson is placed in that time slot.

  - Each lesson lands in exactly one (non-blocked) slot.
  - Teacher / class clash: at most one lesson per slot.
  - Typed capacity: per slot, per required type T, #lessons-needing-T <= #type-T rooms.
  - General capacity: per slot, #general-pool lessons <= #general rooms.
  - Home sharing: classes sharing a home room don't both hold an ordinary lesson at once.
  - Parallel group: grouped lessons (Tysk/Fransk) share a slot.
  - Same-day adjacency (HARD): lessons of the same assignment that fall on the same
    day must occupy consecutive periods (one contiguous block per day).
  - No lunch straddle (HARD): no subject's daily block may span a major break
    (lunch). A big subject forced to appear 3+ times a day stays on one side of
    lunch (it may cross only a short between-period break when unavoidable).
  - Daily cap (HARD): at most 4 lessons of the same assignment per day.
  - Double lessons (HARD): assignments with requires_consecutive get their lessons
    paired two-and-two; each pair sits in two genuinely back-to-back periods —
    barred from any break, not just lunch. An odd leftover lesson is a single.

Objective: place lessons as early in the day as possible — minimize the sum of
(period_number - 1) over all placed lessons — plus a strong penalty per lesson
beyond 2 of the same assignment on one day (1-2 per day is highly preferred).

Concrete rooms are assigned greedily after solving, within each lesson's allowed
room set, honouring a preferred room when compatible and free.
"""
from datetime import datetime, timezone
from collections import defaultdict

# A break longer than this counts as a "major" break (lunch). No subject's
# same-day block of repeated lessons may straddle a major break — not even a
# large subject that has to appear several times a day.
MAJOR_BREAK_MIN = 30
# A requires_consecutive double is stricter still: its two periods must be
# genuinely back-to-back, so it may not span a break longer than this. 0 means
# any scheduled break (including the short between-period ones) is off-limits.
MAX_DOUBLE_BREAK_MIN = 0
# Hard limit on lessons of one assignment per day, and the soft target above
# which each extra same-day lesson is penalised in the objective.
MAX_PER_DAY = 4
PREFERRED_PER_DAY = 2
DAILY_OVERLOAD_WEIGHT = 20
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.config import settings
from app.models.schedule import Schedule, ScheduleStatus


def run_solver(schedule_id: int) -> None:
    """Background task entry point. Opens its own DB session."""
    db = SessionLocal()
    try:
        _solve(schedule_id, db)
    except Exception as e:
        db.rollback()
        schedule = db.get(Schedule, schedule_id)
        if schedule:
            schedule.status = ScheduleStatus.FAILED
            schedule.algorithm_params = {"error": str(e)}
            db.commit()
    finally:
        db.close()


def _solve(schedule_id: int, db: Session) -> None:
    from ortools.sat.python import cp_model
    from app.models.assignment import Assignment
    from app.models.timeslot import TimeSlot
    from app.models.room import Room
    from app.models.subject import Subject
    from app.models.student_class import StudentClass
    from app.models.constraints import TeacherUnavailability, RoomUnavailability, ClassUnavailability, ConstraintType
    from app.models.schedule import ScheduleEntry
    from app.models.elective import ElectiveBand

    schedule = db.get(Schedule, schedule_id)
    if not schedule:
        return

    school_id = schedule.school_id
    assignments = db.query(Assignment).filter(Assignment.school_id == school_id).all()
    slots = db.query(TimeSlot).filter(TimeSlot.school_id == school_id).order_by(TimeSlot.day_of_week, TimeSlot.period_number).all()
    rooms = db.query(Room).filter(Room.school_id == school_id, Room.is_active == True).all()
    subjects = db.query(Subject).filter(Subject.school_id == school_id).all()
    classes = db.query(StudentClass).filter(StudentClass.school_id == school_id).all()
    bands = db.query(ElectiveBand).filter(
        ElectiveBand.school_id == school_id,
        ElectiveBand.academic_year == schedule.academic_year,
    ).all()
    # Only bands that actually have offerings and at least one hour can be scheduled.
    bands = [b for b in bands if b.offerings and b.hours_per_week > 0]

    slot_ids = [s.id for s in slots]
    n_slots = len(slot_ids)
    slot_index = {sid: i for i, sid in enumerate(slot_ids)}
    slot_period = [s.period_number for s in slots]
    # day -> slot indices ordered by period (slots query is ordered by day, period)
    day_slots: dict[int, list[int]] = defaultdict(list)
    for i, s in enumerate(slots):
        day_slots[s.day_of_week].append(i)

    # Successor slot a double lesson may extend into: next period on the same
    # day with at most a short break in between (never across lunch).
    def _minutes(t) -> int:
        return t.hour * 60 + t.minute

    # Adjacent same-day period pairs split by a break, in two tiers:
    #  - major_break_boundaries (lunch): no subject's daily block may straddle.
    #  - any_break_boundaries (any break > 0): requires_consecutive doubles
    #    additionally may not straddle, so their two periods are back-to-back.
    major_break_boundaries: list[tuple[int, int]] = []
    any_break_boundaries: list[tuple[int, int]] = []
    for d, sis in day_slots.items():
        for s_a, s_b in zip(sis, sis[1:]):
            cur, nxt = slots[s_a], slots[s_b]
            if nxt.period_number != cur.period_number + 1:
                continue  # not consecutive periods → no block spans them anyway
            gap = _minutes(nxt.start_time) - _minutes(cur.end_time)
            if gap > MAJOR_BREAK_MIN:
                major_break_boundaries.append((s_a, s_b))
            if gap > MAX_DOUBLE_BREAK_MIN:
                any_break_boundaries.append((s_a, s_b))

    active_room_ids = {r.id for r in rooms}
    room_type_of = {r.id: r.room_type for r in rooms}
    special_subject_ids = {s.id for s in subjects if s.requires_special_room}
    subject_required_type = {s.id: s.required_room_type for s in subjects}
    double_lesson_subject_ids = {s.id for s in subjects if s.double_lessons}

    if n_slots == 0 or not rooms:
        schedule.status = ScheduleStatus.FAILED
        schedule.algorithm_params = {"error": "School has no time slots or no active rooms"}
        db.commit()
        return

    # ── Home rooms ────────────────────────────────────────────────────────────
    home_room_of_class: dict[int, int] = {
        c.id: c.home_room_id
        for c in classes
        if c.home_room_id is not None and c.home_room_id in active_room_ids
    }
    home_room_ids = set(home_room_of_class.values())
    classes_per_home_room: dict[int, list[int]] = defaultdict(list)
    for cid, rid in home_room_of_class.items():
        classes_per_home_room[rid].append(cid)

    # ── Pinned rooms (explicit preferred_room_id) ─────────────────────────────
    # An assignment with a preferred room is hard-pinned to it, overriding the
    # home-room/type logic. Pins to a home room are ignored to avoid clashes.
    pinned_room_of_assignment: dict[int, int] = {
        a.id: a.preferred_room_id
        for a in assignments
        if a.preferred_room_id is not None
        and a.preferred_room_id in active_room_ids
        and a.preferred_room_id not in home_room_ids
    }
    pinned_room_ids = set(pinned_room_of_assignment.values())

    # ── Shared pool, partitioned by room type ─────────────────────────────────
    # Pinned rooms are reserved for their pinned lessons, so exclude them.
    pool_room_ids = [r.id for r in rooms if r.id not in home_room_ids and r.id not in pinned_room_ids]
    required_types = {t for t in subject_required_type.values() if t is not None}

    typed_pool_rooms: dict[object, list[int]] = defaultdict(list)  # RoomType -> room ids
    general_pool_rooms: list[int] = []
    for rid in pool_room_ids:
        rt = room_type_of[rid]
        if rt in required_types:
            typed_pool_rooms[rt].append(rid)
        else:
            general_pool_rooms.append(rid)

    # ── Unavailability (HARD) → blocked slot indices ──────────────────────────
    teacher_blocked: dict[int, set[int]] = defaultdict(set)
    for u in db.query(TeacherUnavailability).join(TimeSlot, TeacherUnavailability.time_slot_id == TimeSlot.id).filter(
        TimeSlot.school_id == school_id,
        TeacherUnavailability.constraint_type == ConstraintType.HARD,
    ).all():
        if u.time_slot_id in slot_index:
            teacher_blocked[u.teacher_id].add(slot_index[u.time_slot_id])

    class_blocked: dict[int, set[int]] = defaultdict(set)
    for u in db.query(ClassUnavailability).join(TimeSlot, ClassUnavailability.time_slot_id == TimeSlot.id).filter(
        TimeSlot.school_id == school_id
    ).all():
        if u.time_slot_id in slot_index:
            class_blocked[u.student_class_id].add(slot_index[u.time_slot_id])

    room_blocked: dict[int, set[int]] = defaultdict(set)  # room_id -> slot indices
    for u in db.query(RoomUnavailability).join(TimeSlot, RoomUnavailability.time_slot_id == TimeSlot.id).filter(
        TimeSlot.school_id == school_id
    ).all():
        if u.time_slot_id in slot_index:
            room_blocked[u.room_id].add(slot_index[u.time_slot_id])

    def rooms_available(room_id_list: list[int], s: int) -> int:
        return sum(1 for rid in room_id_list if s not in room_blocked.get(rid, set()))

    # ── Build flat lesson list with room bucket ───────────────────────────────
    # bucket: ("type", RoomType) | ("general",) | None (home room, not pooled)
    lessons: list[dict] = []
    for a in assignments:
        blocked = teacher_blocked.get(a.teacher_id, set()) | class_blocked.get(a.student_class_id, set())
        has_home = a.student_class_id in home_room_of_class
        rtype = subject_required_type.get(a.subject_id)
        is_special = a.subject_id in special_subject_ids
        pin = pinned_room_of_assignment.get(a.id)
        if pin is not None:
            bucket = ("pin", pin)            # explicit preferred room — hard pin
        elif is_special or not has_home:
            bucket = ("type", rtype) if rtype is not None else ("general",)
        else:
            bucket = None  # ordinary home-room lesson
        for k in range(a.hours_per_week):
            lessons.append({
                "key": (a.id, k),
                "assignment": a,
                "teacher_id": a.teacher_id,
                "class_id": a.student_class_id,
                "blocked": blocked,
                "bucket": bucket,
            })
    n_lessons = len(lessons)

    # ── Elective bands: per band, hours of parallel offerings shared by a grade ──
    # y[(bi, k, s)] = band bi's hour k is placed in slot s. All offerings of a band
    # run in those slots; every active class of the band's grade is blocked there.
    active_class_ids_by_grade: dict[int, list[int]] = defaultdict(list)
    for c in classes:
        if c.is_active:
            active_class_ids_by_grade[c.grade_level].append(c.id)

    band_offerings: list[list] = [list(b.offerings) for b in bands]
    band_hours: list[int] = [b.hours_per_week for b in bands]
    band_classes: list[list[int]] = [active_class_ids_by_grade.get(b.grade_level, []) for b in bands]

    def _offering_pool(rid: int):
        rt = room_type_of.get(rid)
        if rid in typed_pool_rooms.get(rt, []):
            return ("type", rt)
        if rid in general_pool_rooms:
            return ("general",)
        return None  # home / assignment-pinned room: no shared pool to debit

    band_blocked: list[set[int]] = []
    teacher_band_terms: dict[int, list[tuple[int, int]]] = defaultdict(list)
    class_band_terms: dict[int, list[tuple[int, int]]] = defaultdict(list)
    room_bands: dict[int, set[int]] = defaultdict(set)
    typed_band_terms: dict[object, list[tuple[int, int]]] = defaultdict(list)
    general_band_terms: list[tuple[int, int]] = []
    for bi, b in enumerate(bands):
        H = band_hours[bi]
        blk: set[int] = set()
        teachers_in_band: set[int] = set()
        for o in band_offerings[bi]:
            blk |= teacher_blocked.get(o.teacher_id, set())
            blk |= room_blocked.get(o.room_id, set())
            teachers_in_band.add(o.teacher_id)
            room_bands[o.room_id].add(bi)
            pool = _offering_pool(o.room_id)
            for k in range(H):
                if pool is None:
                    continue
                if pool[0] == "type":
                    typed_band_terms[pool[1]].append((bi, k))
                else:
                    general_band_terms.append((bi, k))
        for cid in band_classes[bi]:
            blk |= class_blocked.get(cid, set())
            for k in range(H):
                class_band_terms[cid].append((bi, k))
        for t in teachers_in_band:
            for k in range(H):
                teacher_band_terms[t].append((bi, k))
        band_blocked.append(blk)

    def _has_consecutive_pair(blk: set[int]) -> bool:
        """True if some day has two adjacent (consecutive period) free slots."""
        for sis in day_slots.values():
            for s_a, s_b in zip(sis, sis[1:]):
                if (slots[s_b].period_number == slots[s_a].period_number + 1
                        and s_a not in blk and s_b not in blk):
                    return True
        return False

    # Fast-fail bands that can't physically fit before handing to the solver.
    for bi, b in enumerate(bands):
        H = band_hours[bi]
        free = [s for s in range(n_slots) if s not in band_blocked[bi]]
        ok = len(free) >= H
        if ok and b.requires_consecutive and H >= 2:
            ok = _has_consecutive_pair(band_blocked[bi])
        if not ok:
            schedule.status = ScheduleStatus.FAILED
            schedule.algorithm_params = {
                "error": f"Elective band '{b.name}' (grade {b.grade_level}) can't fit: "
                         f"needs {H} period(s)"
                         + (" with a back-to-back pair" if b.requires_consecutive and H >= 2 else "")
                         + " free of its teachers'/rooms'/classes' unavailability.",
            }
            db.commit()
            return

    if n_lessons == 0 and not bands:
        db.query(ScheduleEntry).filter(ScheduleEntry.schedule_id == schedule_id, ScheduleEntry.is_locked == False).delete()
        schedule.status = ScheduleStatus.COMPLETE
        schedule.generated_at = datetime.now(timezone.utc)
        schedule.algorithm_params = {"note": "no assignments to schedule"}
        db.commit()
        return

    model = cp_model.CpModel()

    # x[(li, s)] = lesson li placed in slot s
    x: dict[tuple[int, int], cp_model.IntVar] = {}
    for li, lesson in enumerate(lessons):
        allowed = []
        for s in range(n_slots):
            var = model.new_bool_var(f"x_{li}_{s}")
            x[(li, s)] = var
            if s in lesson["blocked"]:
                model.add(var == 0)
            else:
                allowed.append(var)
        model.add_exactly_one(allowed)

    # Band-hour vars y[(bi, k, s)]
    y: dict[tuple[int, int, int], cp_model.IntVar] = {}
    for bi in range(len(bands)):
        H = band_hours[bi]
        blk = band_blocked[bi]
        for k in range(H):
            allowed = []
            for s in range(n_slots):
                var = model.new_bool_var(f"y_{bi}_{k}_{s}")
                y[(bi, k, s)] = var
                if s in blk:
                    model.add(var == 0)
                else:
                    allowed.append(var)
            model.add_exactly_one(allowed)
        # symmetry breaking: hour copies occupy strictly increasing slots
        if H > 1:
            slot_expr = [sum(s * y[(bi, k, s)] for s in range(n_slots)) for k in range(H)]
            for prev, nxt in zip(slot_expr, slot_expr[1:]):
                model.add(prev + 1 <= nxt)

    # Teacher / class clash — regular lessons AND band hours compete per slot.
    teacher_lessons: dict[int, list[int]] = defaultdict(list)
    class_lessons: dict[int, list[int]] = defaultdict(list)
    for li, lesson in enumerate(lessons):
        teacher_lessons[lesson["teacher_id"]].append(li)
        class_lessons[lesson["class_id"]].append(li)
    for tid in set(teacher_lessons) | set(teacher_band_terms):
        lis = teacher_lessons.get(tid, [])
        bterms = teacher_band_terms.get(tid, [])
        if len(lis) + len(bterms) <= 1:
            continue
        for s in range(n_slots):
            model.add(
                sum(x[(li, s)] for li in lis)
                + sum(y[(bi, k, s)] for bi, k in bterms) <= 1
            )
    for cid in set(class_lessons) | set(class_band_terms):
        lis = class_lessons.get(cid, [])
        bterms = class_band_terms.get(cid, [])
        if len(lis) + len(bterms) <= 1:
            continue
        for s in range(n_slots):
            model.add(
                sum(x[(li, s)] for li in lis)
                + sum(y[(bi, k, s)] for bi, k in bterms) <= 1
            )

    # Room capacity, per bucket
    typed_lessons: dict[object, list[int]] = defaultdict(list)
    general_lessons: list[int] = []
    for li, lesson in enumerate(lessons):
        b = lesson["bucket"]
        if b is None:
            continue
        if b[0] == "type":
            typed_lessons[b[1]].append(li)
        elif b[0] == "general":
            general_lessons.append(li)
        # "pin" buckets have their own per-room capacity below

    # Typed/general capacity: regular lessons plus any band offering whose pinned
    # room sits in that pool both draw from it (the room stays counted in the pool).
    for rtype in set(typed_lessons) | set(typed_band_terms):
        rlist = typed_pool_rooms.get(rtype, [])
        lis = typed_lessons.get(rtype, [])
        bterms = typed_band_terms.get(rtype, [])
        for s in range(n_slots):
            model.add(
                sum(x[(li, s)] for li in lis)
                + sum(y[(bi, k, s)] for bi, k in bterms) <= rooms_available(rlist, s)
            )

    if general_lessons or general_band_terms:
        for s in range(n_slots):
            model.add(
                sum(x[(li, s)] for li in general_lessons)
                + sum(y[(bi, k, s)] for bi, k in general_band_terms)
                <= rooms_available(general_pool_rooms, s)
            )

    # Pinned-room capacity: a pinned room holds at most one lesson per slot
    pinned_lessons_by_room: dict[int, list[int]] = defaultdict(list)
    for li, lesson in enumerate(lessons):
        b = lesson["bucket"]
        if b is not None and b[0] == "pin":
            pinned_lessons_by_room[b[1]].append(li)
    for rid, lis in pinned_lessons_by_room.items():
        for s in range(n_slots):
            cap = 0 if s in room_blocked.get(rid, set()) else 1
            model.add(sum(x[(li, s)] for li in lis) <= cap)

    # Cross-band per-room cap: two bands pinning the same room can't overlap.
    for rid, bis in room_bands.items():
        terms = [(bi, k) for bi in bis for k in range(band_hours[bi])]
        if len(terms) > 1:
            for s in range(n_slots):
                cap = 0 if s in room_blocked.get(rid, set()) else 1
                model.add(sum(y[(bi, k, s)] for bi, k in terms) <= cap)

    # Home-room sharing
    for rid, cids in classes_per_home_room.items():
        if len(cids) > 1:
            shared = set(cids)
            home_lessons = [
                li for li, lesson in enumerate(lessons)
                if lesson["bucket"] is None and lesson["class_id"] in shared
            ]
            if len(home_lessons) > 1:
                for s in range(n_slots):
                    model.add(sum(x[(li, s)] for li in home_lessons) <= 1)

    # Parallel groups
    key_to_li = {lesson["key"]: li for li, lesson in enumerate(lessons)}
    parallel_groups: dict[int, list[Assignment]] = defaultdict(list)
    for a in assignments:
        if a.parallel_group_id is not None:
            parallel_groups[a.parallel_group_id].append(a)
    for group in parallel_groups.values():
        if len(group) >= 2:
            max_hours = min(a.hours_per_week for a in group)
            ref = group[0]
            for other in group[1:]:
                for k in range(max_hours):
                    li_ref = key_to_li[(ref.id, k)]
                    li_other = key_to_li[(other.id, k)]
                    for s in range(n_slots):
                        model.add(x[(li_ref, s)] == x[(li_other, s)])

    # ── Same-day adjacency + symmetry breaking ────────────────────────────────
    # Lessons of one assignment are interchangeable copies. Order them by slot
    # index (symmetry breaking), and force any copies landing on the same day
    # into consecutive periods: per (assignment, day) the placed periods must
    # form at most one contiguous block. A "block start" at period p means the
    # lesson runs at p but not at p-1; allowing at most one start per day makes
    # the day's copies adjacent.
    assignment_lessons: dict[int, list[int]] = defaultdict(list)
    for li, lesson in enumerate(lessons):
        assignment_lessons[lesson["assignment"].id].append(li)

    overage_vars: list[cp_model.IntVar] = []
    for a_id, lis in assignment_lessons.items():
        if len(lis) < 2:
            continue
        # symmetry breaking: strictly increasing slot index per copy
        slot_expr = [sum(s * x[(li, s)] for s in range(n_slots)) for li in lis]
        for prev, nxt in zip(slot_expr, slot_expr[1:]):
            model.add(prev + 1 <= nxt)
        a0 = lessons[lis[0]]["assignment"]
        # A subject flagged double_lessons applies to every school; the per-
        # assignment requires_consecutive flag is kept as an optional override.
        is_consecutive = a0.subject_id in double_lesson_subject_ids or a0.requires_consecutive

        # double lessons (requires_consecutive): pair copies (0,1), (2,3), ...
        # onto the SAME day. The per-day contiguity constraint below then forces
        # each pair into two adjacent periods — a real 2-period block. A 4h
        # assignment splits into two such pairs (kept apart across days by the
        # overload penalty); a 3h one leaves a single leftover lesson.
        if is_consecutive:
            for p in range(len(lis) // 2):
                first, second = lis[2 * p], lis[2 * p + 1]
                for d in day_slots:
                    model.add(
                        sum(x[(first, si)] for si in day_slots[d])
                        == sum(x[(second, si)] for si in day_slots[d])
                    )

        # HARD no-straddle: a same-day block may not occupy both sides of a break
        # it isn't allowed to cross. Every subject is barred from straddling a
        # major break (lunch); a requires_consecutive double is barred from any
        # break, so its two periods are genuinely back-to-back. This covers the
        # whole daily block — the seam between pairs and odd leftover lessons
        # included. occ on either side is <= 1 (all copies share one class,
        # capped by the class-clash rule), so a simple sum works.
        block_boundaries = any_break_boundaries if is_consecutive else major_break_boundaries
        for s_a, s_b in block_boundaries:
            model.add(
                sum(x[(li, s_a)] for li in lis) + sum(x[(li, s_b)] for li in lis) <= 1
            )
        # per day: contiguity, hard cap, and overload beyond the preferred count
        for d, day_sis in day_slots.items():
            occupied = [sum(x[(li, s)] for li in lis) for s in day_sis]
            starts = []
            for i, occ in enumerate(occupied):
                st = model.new_bool_var(f"blockstart_{a_id}_{d}_{i}")
                if i == 0:
                    model.add(st >= occ)
                else:
                    model.add(st >= occ - occupied[i - 1])
                starts.append(st)
            model.add(sum(starts) <= 1)
            day_count = sum(occupied)
            if len(lis) > MAX_PER_DAY:
                model.add(day_count <= MAX_PER_DAY)
            if len(lis) > PREFERRED_PER_DAY:
                over = model.new_int_var(0, MAX_PER_DAY - PREFERRED_PER_DAY, f"over_{a_id}_{d}")
                model.add(over >= day_count - PREFERRED_PER_DAY)
                overage_vars.append(over)

    # ── Per-band contiguity / double pairing (same shape as assignments) ──────
    for bi in range(len(bands)):
        H = band_hours[bi]
        if H < 2:
            continue
        is_consecutive = bands[bi].requires_consecutive
        if is_consecutive:
            # pair hours (0,1),(2,3)… onto the same day so each becomes a real double
            for p in range(H // 2):
                first, second = 2 * p, 2 * p + 1
                for d in day_slots:
                    model.add(
                        sum(y[(bi, first, si)] for si in day_slots[d])
                        == sum(y[(bi, second, si)] for si in day_slots[d])
                    )
        block_boundaries = any_break_boundaries if is_consecutive else major_break_boundaries
        for s_a, s_b in block_boundaries:
            model.add(
                sum(y[(bi, k, s_a)] for k in range(H))
                + sum(y[(bi, k, s_b)] for k in range(H)) <= 1
            )
        for d, day_sis in day_slots.items():
            occupied = [sum(y[(bi, k, s)] for k in range(H)) for s in day_sis]
            starts = []
            for i, occ in enumerate(occupied):
                st = model.new_bool_var(f"bandstart_{bi}_{d}_{i}")
                if i == 0:
                    model.add(st >= occ)
                else:
                    model.add(st >= occ - occupied[i - 1])
                starts.append(st)
            model.add(sum(starts) <= 1)

    # ── Objective: early mornings, and avoid overload days ───────────────────
    # (Long-break straddling of doubles is now a hard constraint, not a penalty.)
    model.minimize(
        sum(
            (slot_period[s] - 1) * x[(li, s)]
            for li, lesson in enumerate(lessons)
            for s in range(n_slots)
            if s not in lesson["blocked"]
        )
        + sum(
            (slot_period[s] - 1) * y[(bi, k, s)]
            for bi in range(len(bands))
            for k in range(band_hours[bi])
            for s in range(n_slots)
            if s not in band_blocked[bi]
        )
        + DAILY_OVERLOAD_WEIGHT * sum(overage_vars)
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = settings.solver_max_time_seconds
    # Default 1 worker: on a fractional-CPU host more workers just oversubscribe and
    # add memory/thread overhead. Configurable via SOLVER_NUM_WORKERS.
    solver.parameters.num_search_workers = settings.solver_num_workers
    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        schedule.status = ScheduleStatus.FAILED
        schedule.algorithm_params = {
            "or_tools_status": solver.status_name(status),
            "hint": "INFEASIBLE usually means not enough rooms of a required type "
                    "(e.g. too many Idræt lessons for the gyms), the shared pool is "
                    "overfull, hard unavailabilities leave no valid placement, or an "
                    "assignment has too many weekly hours to fit as contiguous "
                    "same-day blocks."
                    + (f" Elective bands in play: {', '.join(b.name for b in bands)}." if bands else ""),
        }
        db.commit()
        return

    # ── Decode: slot index per lesson ─────────────────────────────────────────
    lesson_slot_idx: dict[int, int] = {}
    for li in range(n_lessons):
        for s in range(n_slots):
            if solver.boolean_value(x[(li, s)]):
                lesson_slot_idx[li] = s
                break

    # Decode band hours → slot, and the offering rooms occupied at each slot.
    band_slot: dict[tuple[int, int], int] = {}
    band_rooms_at_slot: dict[int, list[int]] = defaultdict(list)
    for bi in range(len(bands)):
        for k in range(band_hours[bi]):
            for s in range(n_slots):
                if solver.boolean_value(y[(bi, k, s)]):
                    band_slot[(bi, k)] = s
                    for o in band_offerings[bi]:
                        band_rooms_at_slot[s].append(o.room_id)
                    break

    # ── Greedy room assignment per slot, within each lesson's allowed rooms ────
    by_slot: dict[int, list[int]] = defaultdict(list)
    for li, s in lesson_slot_idx.items():
        by_slot[s].append(li)

    lesson_room_id: dict[int, int] = {}
    for s, lis in by_slot.items():
        # Reserve band offering rooms FIRST so regular lessons don't grab them.
        used_by_pool: set[int] = set(band_rooms_at_slot.get(s, []))

        def assign_from(candidates: list[int], room_pool: list[int]):
            available = [rid for rid in room_pool if s not in room_blocked.get(rid, set()) and rid not in used_by_pool]
            # preferred first
            for li in candidates:
                pref = lessons[li]["assignment"].preferred_room_id
                if pref is not None and pref in available:
                    lesson_room_id[li] = pref
                    available.remove(pref)
                    used_by_pool.add(pref)
            fi = 0
            for li in candidates:
                if li in lesson_room_id:
                    continue
                lesson_room_id[li] = available[fi]
                used_by_pool.add(available[fi])
                fi += 1

        # pinned lessons → their exact room
        for li in lis:
            b = lessons[li]["bucket"]
            if b is not None and b[0] == "pin":
                lesson_room_id[li] = b[1]
        # home lessons → home room
        for li in lis:
            if lessons[li]["bucket"] is None:
                lesson_room_id[li] = home_room_of_class[lessons[li]["class_id"]]
        # typed lessons → matching type rooms
        for rtype in required_types:
            cands = [li for li in lis if lessons[li]["bucket"] == ("type", rtype)]
            if cands:
                assign_from(cands, typed_pool_rooms.get(rtype, []))
        # general lessons → general rooms
        gen_cands = [li for li in lis if lessons[li]["bucket"] == ("general",)]
        if gen_cands:
            assign_from(gen_cands, general_pool_rooms)

    # ── Write entries (clear non-locked first) ────────────────────────────────
    db.query(ScheduleEntry).filter(ScheduleEntry.schedule_id == schedule_id, ScheduleEntry.is_locked == False).delete()

    not_in_preferred = 0
    pool_count = len(general_lessons) + sum(len(v) for v in typed_lessons.values()) + sum(len(v) for v in pinned_lessons_by_room.values())
    for li, lesson in enumerate(lessons):
        a = lesson["assignment"]
        s_idx = lesson_slot_idx[li]
        rid = lesson_room_id[li]
        if a.preferred_room_id and a.preferred_room_id != rid:
            not_in_preferred += 1
        db.add(ScheduleEntry(
            schedule_id=schedule_id,
            assignment_id=a.id,
            time_slot_id=slot_ids[s_idx],
            room_id=rid,
        ))

    # Band offerings: one entry per offering per band-hour (its pinned room).
    band_entries = 0
    for (bi, k), s_idx in band_slot.items():
        for o in band_offerings[bi]:
            db.add(ScheduleEntry(
                schedule_id=schedule_id,
                assignment_id=None,
                elective_offering_id=o.id,
                time_slot_id=slot_ids[s_idx],
                room_id=o.room_id,
            ))
            band_entries += 1

    schedule.status = ScheduleStatus.COMPLETE
    schedule.generated_at = datetime.now(timezone.utc)
    schedule.score = None
    schedule.algorithm_params = {
        "or_tools_status": solver.status_name(status),
        "wall_time": solver.wall_time,
        "lessons_scheduled": n_lessons,
        "pool_lessons": pool_count,
        "lessons_not_in_preferred_room": not_in_preferred,
        "elective_bands": len(bands),
        "elective_band_entries": band_entries,
        "objective": solver.objective_value,
        "objective_best_bound": solver.best_objective_bound,
        "daily_overload_lessons": sum(solver.value(v) for v in overage_vars),
    }
    db.commit()

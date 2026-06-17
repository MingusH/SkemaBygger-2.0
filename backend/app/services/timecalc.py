"""Shared time/clock helpers for the bell schedule.

A scheduled period occupies more wall-clock time than its 45-minute lesson: the
break that follows it (until the next period the same day) is part of the school
day. `clock_hours_per_period` measures that real per-period clock time so that
"delivered hours" and the auto-assign target both reflect the actual school day,
including breaks — matching the ministry yearly totals (which include breaks)."""

LESSON_TO_CLOCK = 0.75   # one 45-min lesson = 0.75 clock hours (teaching only)
STANDARD_WEEKS = 40      # ministry figures are based on a 40-week school year


def _minutes(t) -> int:
    return t.hour * 60 + t.minute


def clock_hours_per_period(slots, fallback: float = LESSON_TO_CLOCK) -> float:
    """Average real clock hours one scheduled period occupies, INCLUDING the break
    that follows it (gap to the next period the same day). The break after the last
    period of a day is not counted. `slots` are TimeSlot rows. Falls back to a bare
    45-min lesson when there is no bell schedule."""
    by_day: dict[int, list] = {}
    for t in slots:
        by_day.setdefault(t.day_of_week, []).append(t)
    total_min = 0.0
    n = 0
    for day_slots in by_day.values():
        day_slots.sort(key=lambda x: x.period_number)
        for i, t in enumerate(day_slots):
            dur = _minutes(t.end_time) - _minutes(t.start_time)
            gap = 0
            if i + 1 < len(day_slots):
                gap = max(0, _minutes(day_slots[i + 1].start_time) - _minutes(t.end_time))
            total_min += dur + gap
            n += 1
    return (total_min / n / 60.0) if n else fallback


def clock_hours_from_slots(slots) -> tuple[float, dict[int, float]]:
    """Real clock hours a class spends in school, from the periods it actually
    attends in a schedule. Per day: sum each period's duration plus the break to
    the next period ONLY when the two are consecutive (period_number differs by 1);
    a mid-day empty slot (a free period the class doesn't have) is NOT counted.

    `slots` are the distinct TimeSlot rows the class attends. Returns
    (weekly_clock_hours, {day_of_week: clock_hours})."""
    by_day: dict[int, list] = {}
    for t in slots:
        by_day.setdefault(t.day_of_week, []).append(t)

    day_hours: dict[int, float] = {}
    for day, day_slots in by_day.items():
        day_slots.sort(key=lambda x: x.period_number)
        total_min = 0.0
        for i, t in enumerate(day_slots):
            total_min += _minutes(t.end_time) - _minutes(t.start_time)
            if i + 1 < len(day_slots):
                nxt = day_slots[i + 1]
                if nxt.period_number == t.period_number + 1:
                    total_min += max(0, _minutes(nxt.start_time) - _minutes(t.end_time))
        day_hours[day] = total_min / 60.0

    weekly = sum(day_hours.values())
    return weekly, day_hours

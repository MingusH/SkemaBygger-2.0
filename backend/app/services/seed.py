"""
Seed subjects for a school from the Danish ministry PDF.
Idempotent: calling twice won't duplicate subjects.
"""
from sqlalchemy.orm import Session
from app.models.subject import Subject, ElectiveSlotMeta, MinistryHours, SubjectCategory
from app.models.room import RoomType
from app.models.grade_minimums import GradeMinimumHours
from app.services.pdf_parser import MinistryPDFParser

MINISTRY_URL = "https://uvm.dk/media/dfnbhhem/241218-timetalsoversigt-for-skoleaaret-2026-2027-pdf.pdf"

# Default colors per category for the UI
_CATEGORY_COLORS: dict[str, str] = {
    "humanistisk":    "#4f83cc",
    "naturfag":       "#3d9970",
    "praktisk_musisk": "#e67e22",
    "valgfag":        "#9b59b6",
}

# Which physical room type each special subject must be taught in.
# Keyed by Danish subject name (matched case-insensitively, substring-tolerant).
_SUBJECT_ROOM_TYPE: dict[str, RoomType] = {
    "idræt":               RoomType.GYM,
    "fysik/kemi":          RoomType.SCIENCE_LAB,
    "natur/teknologi":     RoomType.SCIENCE_LAB,
    "madkundskab":         RoomType.KITCHEN,
    "håndværk og design":  RoomType.WORKSHOP,
    "musik":               RoomType.MUSIC,
    "billedkunst":         RoomType.ART,
}


def _room_type_for(name: str) -> RoomType | None:
    key = name.strip().lower()
    if key in _SUBJECT_ROOM_TYPE:
        return _SUBJECT_ROOM_TYPE[key]
    # tolerate minor naming variants (e.g. "Natur/teknologi (1.-6.)")
    for subject_name, rtype in _SUBJECT_ROOM_TYPE.items():
        if key.startswith(subject_name):
            return rtype
    return None


# Subjects always taught as back-to-back double lessons. Matched the same way as
# room types so it applies to every school that seeds these subjects.
_DOUBLE_LESSON_SUBJECTS = (
    "idræt", "natur/teknologi", "madkundskab", "håndværk og design", "billedkunst",
)


def _is_double_lesson(name: str) -> bool:
    key = name.strip().lower()
    return any(key.startswith(s) for s in _DOUBLE_LESSON_SUBJECTS)


def seed_subjects_for_school(school_id: int, db: Session) -> int:
    """Download ministry data and upsert subjects + ministry_hours for the given school.
    Returns number of subjects seeded (created, not updated)."""
    parser = MinistryPDFParser()
    data = parser.parse_ministry_pdf(MINISTRY_URL)
    if "error" in data:
        raise RuntimeError(f"PDF parse failed: {data['error']}")

    seeded = 0
    # Mandatory subjects are seeded in PDF order (Dansk, Matematik, ...), which is a
    # sensible default priority for surplus-hour distribution. New subjects only.
    priority_counter = 0

    def _upsert_subject(name: str, short_code: str, category: str, requires_special: bool,
                        is_elective: bool, grade_hours: dict[int, float],
                        slot_key: str | None = None, has_exam: bool = False) -> int:
        existing = db.query(Subject).filter(
            Subject.school_id == school_id, Subject.name == name
        ).first()

        room_type = _room_type_for(name)
        needs_special = requires_special or room_type is not None

        if not existing:
            nonlocal priority_counter
            priority_counter += 1
            subj = Subject(
                school_id=school_id,
                name=name,
                short_code=short_code,
                category=SubjectCategory(category),
                color_hex=_CATEGORY_COLORS.get(category),
                requires_special_room=needs_special,
                required_room_type=room_type,
                is_elective_slot=is_elective,
                double_lessons=_is_double_lesson(name),
                priority=priority_counter,
            )
            db.add(subj)
            db.flush()
            nonlocal seeded
            seeded += 1
        else:
            subj = existing
            # Backfill room-type + double-lesson mapping on re-seed (idempotent reset from UVM)
            subj.required_room_type = room_type
            if room_type is not None:
                subj.requires_special_room = True
            subj.double_lessons = _is_double_lesson(name)

        # Upsert elective meta
        if is_elective and slot_key:
            meta = db.query(ElectiveSlotMeta).filter_by(subject_id=subj.id).first()
            if not meta:
                db.add(ElectiveSlotMeta(subject_id=subj.id, slot_key=slot_key, has_exam=has_exam))

        # Upsert per-grade hours (grades 1-9 only)
        for grade in range(1, 10):
            hours = grade_hours.get(grade, 0.0)
            row = db.query(MinistryHours).filter_by(subject_id=subj.id, grade=grade).first()
            if not row:
                db.add(MinistryHours(subject_id=subj.id, grade=grade, hours_per_week=hours))
            else:
                row.hours_per_week = hours

        return subj.id

    # Mandatory subjects
    for name, meta in data["mandatory_subjects"].items():
        _upsert_subject(
            name=name,
            short_code=meta["short_code"],
            category=meta["category"],
            requires_special=meta.get("requires_special_room", False),
            is_elective=False,
            grade_hours=meta["grade_hours"],
        )

    # Elective slots
    for name, meta in data["electives"].items():
        _upsert_subject(
            name=name,
            short_code=meta["slot_key"][:8].upper(),
            category=meta["category"],
            requires_special=False,
            is_elective=True,
            grade_hours=meta["grade_hours"],
            slot_key=meta["slot_key"],
            has_exam=meta["has_exam"],
        )

    # Upsert grade-level ministry totals (annual_minimum, timebank, total) for grades 0-9
    grade_totals = data.get("grade_totals", {})
    for grade in range(0, 10):
        row = db.query(GradeMinimumHours).filter_by(grade=grade).first()
        values = dict(
            annual_minimum=grade_totals.get("annual_minimum", {}).get(grade, 0.0),
            timebank_hours=grade_totals.get("timebank_and_breaks", {}).get(grade, 0.0),
            total_annual=grade_totals.get("total_annual_time", {}).get(grade, 0.0),
        )
        if not row:
            db.add(GradeMinimumHours(grade=grade, **values))
        else:
            for k, v in values.items():
                setattr(row, k, v)

    db.commit()
    return seeded

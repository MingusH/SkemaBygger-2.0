r"""
SkemaBygger MCP Server (authenticated, remote HTTP transport)
Exposes school data as MCP tools so an AI assistant can read and mutate it — but
only for schools the authenticated user belongs to.

AUTH MODEL
----------
The server runs over HTTP and requires a Bearer token on every request. The token
is an ordinary SkemaBygger JWT — the same one POST /api/auth/token mints — verified
here with the shared secret_key (HS256). Each tool then resolves the token to a User
and enforces the same per-school rules as the REST API:
  - read/list tools  -> caller must be a MEMBER of that school
  - add/delete/bulk   -> caller must be an ADMIN of that school
  - superadmins bypass the per-school checks
list_schools only returns schools the caller is a member of.

RUNNING
-------
This server is mounted into the main FastAPI app (see app/main.py) and served at
`/mcp/` on the same port — one service, one port (fits Render's model). Locally that's
http://localhost:8000/mcp/. Running `python -m app.mcp_server` (below) starts it as a
standalone HTTP server on port 8001 instead; that's optional, only for isolated testing.

CONNECTING A CLIENT (e.g. Claude Desktop)
-----------------------------------------
Point the client at the /mcp/ URL and send a Bearer token. Generate a long-lived,
revocable personal access token in the web app (the "Adgangstokens" page) and use it:
    {
      "mcpServers": {
        "skemabygger": {
          "url": "https://your-host/mcp/",
          "headers": { "Authorization": "Bearer skb_..." }
        }
      }
    }
A short-lived login JWT from /api/auth/token also works but expires after ~1 day.
"""

import hashlib
from contextlib import contextmanager
from datetime import time, datetime, timezone

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AccessToken, MultiAuth, TokenVerifier
from fastmcp.server.dependencies import get_access_token
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.school import School
from app.models.subject import Subject
from app.models.teacher import Teacher, TeacherSubject
from app.models.room import Room
from app.models.assignment import Assignment
from app.models.student_class import StudentClass
from app.models.timeslot import TimeSlot
from app.models.user import User, SchoolMember, UserRole, PersonalAccessToken
from app.services.oauth_provider import DBOAuthProvider


@contextmanager
def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class PATVerifier(TokenVerifier):
    """Validate long-lived personal access tokens (prefix 'skb_'). The DB stores only
    the SHA-256 hash; we look it up, check expiry, and record last_used_at. Returns the
    user's email in the 'sub' claim so the tools resolve identity the same way as JWTs."""

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token.startswith("skb_"):
            return None
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with get_db() as db:
            pat = db.query(PersonalAccessToken).filter(PersonalAccessToken.token_hash == token_hash).first()
            if not pat:
                return None
            if pat.expires_at and pat.expires_at < datetime.now(timezone.utc):
                return None
            user = db.get(User, pat.user_id)
            if not user or not user.is_active:
                return None
            pat.last_used_at = datetime.now(timezone.utc)
            db.commit()
            return AccessToken(token=token, client_id=str(user.id), scopes=[], claims={"sub": user.email})


# Auth: a self-hosted OAuth 2.1 server (Claude Desktop "sign in" flow) PLUS long-lived
# personal access tokens. The OAuth provider both serves the OAuth routes and verifies
# its access tokens; PATVerifier handles 'skb_' tokens.
_auth = MultiAuth(
    server=DBOAuthProvider(base_url=settings.public_base_url),
    verifiers=[PATVerifier()],
)
mcp = FastMCP("SkemaBygger", auth=_auth)


# ── Identity & authorization ──────────────────────────────────────────────────

def _current_user(db: Session) -> User:
    """Resolve the caller from the verified Bearer token. The JWT 'sub' claim holds
    the user's email (see app/routers/auth.py)."""
    try:
        token = get_access_token()
    except Exception:
        token = None
    email = (token.claims or {}).get("sub") if token else None
    if not email:
        raise ToolError("Not authenticated — connect with a valid Bearer token.")
    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if not user:
        raise ToolError("Authenticated user not found or inactive.")
    return user


def _require_member(db: Session, user: User, school_id: int, *, admin: bool) -> None:
    """Enforce that the user may act on this school. Mirrors the REST API's
    require_school_member / require_school_admin dependencies."""
    if user.is_superadmin:
        return
    member = (
        db.query(SchoolMember)
        .filter(SchoolMember.school_id == school_id, SchoolMember.user_id == user.id)
        .first()
    )
    if not member:
        raise ToolError(f"You are not a member of school {school_id}.")
    if admin and member.role != UserRole.ADMIN:
        raise ToolError(f"Admin role required to modify school {school_id}.")


def _parse_time(s: str) -> time:
    """Parse 'HH:MM' or 'HH:MM:SS' (also tolerates '8:00') into a time."""
    parts = str(s).strip().split(":")
    return time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0, int(parts[2]) if len(parts) > 2 else 0)


def _fmt_time(t: time | None) -> str | None:
    return t.strftime("%H:%M") if t else None


# ── Schools ───────────────────────────────────────────────────────────────────

@mcp.tool()
def list_schools() -> list[dict]:
    """List the schools you may access. Use this first to find the school_id you need."""
    with get_db() as db:
        user = _current_user(db)
        q = db.query(School)
        if not user.is_superadmin:
            ids = [m.school_id for m in db.query(SchoolMember).filter(SchoolMember.user_id == user.id).all()]
            q = q.filter(School.id.in_(ids))
        return [
            {"id": s.id, "name": s.name, "short_name": s.short_name, "academic_year": s.academic_year}
            for s in q.all()
        ]


# ── Subjects ──────────────────────────────────────────────────────────────────

@mcp.tool()
def list_subjects(school_id: int) -> list[dict]:
    """List all subjects for a school. Use subject IDs when adding teachers with qualifications."""
    with get_db() as db:
        _require_member(db, _current_user(db), school_id, admin=False)
        subjects = db.query(Subject).filter(Subject.school_id == school_id).all()
        return [
            {
                "id": s.id,
                "name": s.name,
                "short_code": s.short_code,
                "category": s.category.value if hasattr(s.category, "value") else s.category,
                "is_elective_slot": s.is_elective_slot,
            }
            for s in subjects
        ]


# ── Teachers ──────────────────────────────────────────────────────────────────

@mcp.tool()
def list_teachers(school_id: int) -> list[dict]:
    """List all teachers for a school including their subject qualifications."""
    with get_db() as db:
        _require_member(db, _current_user(db), school_id, admin=False)
        teachers = db.query(Teacher).filter(Teacher.school_id == school_id).all()
        return [
            {
                "id": t.id,
                "first_name": t.first_name,
                "last_name": t.last_name,
                "short_code": t.short_code,
                "email": t.email,
                "max_hours_per_week": t.max_hours_per_week,
                "is_active": t.is_active,
                "subject_ids": [ts.subject_id for ts in t.teacher_subjects],
            }
            for t in teachers
        ]


@mcp.tool()
def add_teacher(
    school_id: int,
    first_name: str,
    last_name: str,
    short_code: str,
    subject_ids: list[int],
    email: str = "",
    max_hours_per_week: int = 0,
) -> dict:
    """Add a new teacher to a school and assign subject qualifications. (Requires admin.)
    subject_ids: list of subject IDs the teacher is qualified to teach (use list_subjects to find IDs).
    max_hours_per_week: 0 means no limit.
    """
    with get_db() as db:
        _require_member(db, _current_user(db), school_id, admin=True)
        teacher = Teacher(
            school_id=school_id,
            first_name=first_name,
            last_name=last_name,
            short_code=short_code,
            email=email or None,
            max_hours_per_week=max_hours_per_week or None,
        )
        db.add(teacher)
        db.flush()
        for sid in subject_ids:
            db.add(TeacherSubject(teacher_id=teacher.id, subject_id=sid))
        db.commit()
        db.refresh(teacher)
        return {
            "id": teacher.id,
            "first_name": teacher.first_name,
            "last_name": teacher.last_name,
            "short_code": teacher.short_code,
            "subject_ids": subject_ids,
        }


@mcp.tool()
def bulk_add_teachers(school_id: int, teachers: list[dict]) -> dict:
    """Add multiple teachers to a school at once. (Requires admin.)
    teachers: list of dicts, each with:
      {"first_name": str, "last_name": str, "short_code": str,
       "subject_ids": [int, ...],            # subjects this teacher can teach (use list_subjects)
       "email": str,                          # optional
       "max_hours_per_week": int}            # optional, 0 = no limit
    Each row is validated independently; valid rows are created and invalid ones are
    reported in "errors" (no row blocks the others). Returns created teachers and errors.
    """
    created: list[dict] = []
    errors: list[dict] = []
    with get_db() as db:
        _require_member(db, _current_user(db), school_id, admin=True)
        valid_subject_ids = {s.id for s in db.query(Subject).filter(Subject.school_id == school_id).all()}
        for i, t in enumerate(teachers):
            first = (t.get("first_name") or "").strip()
            last = (t.get("last_name") or "").strip()
            code = (t.get("short_code") or "").strip()
            if not first or not last or not code:
                errors.append({"index": i, "error": "first_name, last_name and short_code are required"})
                continue
            sids = t.get("subject_ids") or []
            unknown = [s for s in sids if s not in valid_subject_ids]
            if unknown:
                errors.append({"index": i, "short_code": code, "error": f"subject_ids not in this school: {unknown}"})
                continue
            teacher = Teacher(
                school_id=school_id,
                first_name=first,
                last_name=last,
                short_code=code,
                email=(t.get("email") or None),
                max_hours_per_week=(t.get("max_hours_per_week") or None),
            )
            db.add(teacher)
            db.flush()
            for s in sids:
                db.add(TeacherSubject(teacher_id=teacher.id, subject_id=s))
            created.append({"id": teacher.id, "short_code": code, "name": f"{first} {last}", "subject_ids": sids})
        db.commit()
    return {"created_count": len(created), "created": created, "errors": errors}


@mcp.tool()
def delete_teacher(school_id: int, teacher_id: int) -> dict:
    """Delete a teacher and all their assignments from a school. (Requires admin.)"""
    with get_db() as db:
        _require_member(db, _current_user(db), school_id, admin=True)
        teacher = db.query(Teacher).filter(Teacher.id == teacher_id, Teacher.school_id == school_id).first()
        if not teacher:
            return {"error": f"Teacher {teacher_id} not found in school {school_id}"}
        name = f"{teacher.first_name} {teacher.last_name}"
        db.delete(teacher)
        db.commit()
        return {"deleted": True, "teacher": name}


# ── Rooms ─────────────────────────────────────────────────────────────────────

VALID_ROOM_TYPES = ["STANDARD", "GYM", "SCIENCE_LAB", "COMPUTER", "MUSIC", "WORKSHOP", "KITCHEN", "OTHER"]


@mcp.tool()
def list_rooms(school_id: int) -> list[dict]:
    """List all rooms for a school."""
    with get_db() as db:
        _require_member(db, _current_user(db), school_id, admin=False)
        rooms = db.query(Room).filter(Room.school_id == school_id).all()
        return [
            {
                "id": r.id,
                "name": r.name,
                "short_code": r.short_code,
                "capacity": r.capacity,
                "room_type": r.room_type.value if hasattr(r.room_type, "value") else r.room_type,
                "is_active": r.is_active,
            }
            for r in rooms
        ]


@mcp.tool()
def add_room(
    school_id: int,
    name: str,
    short_code: str,
    capacity: int,
    room_type: str = "STANDARD",
) -> dict:
    """Add a new room to a school. (Requires admin.)
    room_type must be one of: STANDARD, GYM, SCIENCE_LAB, COMPUTER, MUSIC, WORKSHOP, KITCHEN, OTHER.
    """
    if room_type not in VALID_ROOM_TYPES:
        return {"error": f"Invalid room_type '{room_type}'. Must be one of: {', '.join(VALID_ROOM_TYPES)}"}
    with get_db() as db:
        _require_member(db, _current_user(db), school_id, admin=True)
        room = Room(
            school_id=school_id,
            name=name,
            short_code=short_code,
            capacity=capacity,
            room_type=room_type,
        )
        db.add(room)
        db.commit()
        db.refresh(room)
        return {"id": room.id, "name": room.name, "short_code": room.short_code, "capacity": room.capacity, "room_type": room_type}


@mcp.tool()
def delete_room(school_id: int, room_id: int) -> dict:
    """Delete a room from a school. (Requires admin.)"""
    with get_db() as db:
        _require_member(db, _current_user(db), school_id, admin=True)
        room = db.query(Room).filter(Room.id == room_id, Room.school_id == school_id).first()
        if not room:
            return {"error": f"Room {room_id} not found in school {school_id}"}
        name = room.name
        db.delete(room)
        db.commit()
        return {"deleted": True, "room": name}


# ── Assignments ───────────────────────────────────────────────────────────────

@mcp.tool()
def list_assignments(school_id: int, class_id: int = 0) -> list[dict]:
    """List assignments for a school, optionally filtered by class_id (0 = all classes).
    Returns subject name, teacher name, class name, hours/week, and current preferred_room_id.
    Use list_rooms to find room IDs for bulk_set_preferred_rooms.
    """
    with get_db() as db:
        _require_member(db, _current_user(db), school_id, admin=False)
        q = db.query(Assignment).filter(Assignment.school_id == school_id)
        if class_id:
            q = q.filter(Assignment.student_class_id == class_id)
        assignments = q.all()

        subject_map = {s.id: s for s in db.query(Subject).filter(Subject.school_id == school_id).all()}
        teacher_map = {t.id: t for t in db.query(Teacher).filter(Teacher.school_id == school_id).all()}
        class_map = {c.id: c for c in db.query(StudentClass).filter(StudentClass.school_id == school_id).all()}
        room_map = {r.id: r for r in db.query(Room).filter(Room.school_id == school_id).all()}

        return [
            {
                "id": a.id,
                "class": class_map[a.student_class_id].name if a.student_class_id in class_map else a.student_class_id,
                "subject": subject_map[a.subject_id].name if a.subject_id in subject_map else a.subject_id,
                "subject_requires_special_room": subject_map[a.subject_id].requires_special_room if a.subject_id in subject_map else None,
                "teacher": f"{teacher_map[a.teacher_id].first_name} {teacher_map[a.teacher_id].last_name}" if a.teacher_id in teacher_map else a.teacher_id,
                "hours_per_week": a.hours_per_week,
                "preferred_room_id": a.preferred_room_id,
                "preferred_room": room_map[a.preferred_room_id].name if a.preferred_room_id and a.preferred_room_id in room_map else None,
            }
            for a in assignments
        ]


@mcp.tool()
def bulk_set_preferred_rooms(school_id: int, mappings: list[dict]) -> dict:
    """Set preferred_room_id on multiple assignments at once. (Requires admin.)
    mappings: list of {"assignment_id": <int>, "room_id": <int or null>}
    Use list_assignments to find assignment IDs and list_rooms to find room IDs.
    Set room_id to null to clear a preferred room.
    Returns counts of updated and not-found assignments.
    """
    updated = 0
    not_found = 0
    with get_db() as db:
        _require_member(db, _current_user(db), school_id, admin=True)
        for m in mappings:
            a = db.query(Assignment).filter(
                Assignment.id == m["assignment_id"],
                Assignment.school_id == school_id,
            ).first()
            if a is None:
                not_found += 1
                continue
            a.preferred_room_id = m.get("room_id")
            updated += 1
        db.commit()
    return {"updated": updated, "not_found": not_found}


# ── Lektioner / time slots (the weekly bell schedule) ─────────────────────────
# A "lektion" is one period in the weekly grid: a day, a period number, and a
# start/end time. A BREAK is not its own row — it's the gap between one period's
# end_time and the next period's start_time on the same day. To make a longer break,
# move the following period's start_time later; to shorten it, move it earlier.


@mcp.tool()
def list_timeslots(school_id: int) -> list[dict]:
    """List the school's lektioner (periods) for the weekly bell schedule, ordered by day and period.
    day_of_week: 1=Monday .. 5=Friday. Times are 'HH:MM'. break_after_minutes is the gap between this
    period's end and the next period's start on the same day (the break the pupils get after it)."""
    with get_db() as db:
        _require_member(db, _current_user(db), school_id, admin=False)
        slots = (
            db.query(TimeSlot)
            .filter(TimeSlot.school_id == school_id)
            .order_by(TimeSlot.day_of_week, TimeSlot.period_number)
            .all()
        )
        by_day: dict[int, list[TimeSlot]] = {}
        for s in slots:
            by_day.setdefault(s.day_of_week, []).append(s)
        out: list[dict] = []
        for day_slots in by_day.values():
            for i, s in enumerate(day_slots):
                brk = None
                if i + 1 < len(day_slots):
                    end_min = s.end_time.hour * 60 + s.end_time.minute
                    nxt_min = day_slots[i + 1].start_time.hour * 60 + day_slots[i + 1].start_time.minute
                    brk = max(0, nxt_min - end_min)
                out.append({
                    "id": s.id,
                    "day_of_week": s.day_of_week,
                    "period_number": s.period_number,
                    "start_time": _fmt_time(s.start_time),
                    "end_time": _fmt_time(s.end_time),
                    "label": s.label,
                    "break_after_minutes": brk,
                })
        return out


@mcp.tool()
def add_timeslot(
    school_id: int,
    day_of_week: int,
    period_number: int,
    start_time: str,
    end_time: str,
    label: str = "",
) -> dict:
    """Add one lektion (period) to the weekly schedule. (Requires admin.)
    day_of_week: 1=Monday .. 5=Friday. start_time/end_time as 'HH:MM' (e.g. '08:00').
    Each (day_of_week, period_number) must be unique — use update_timeslot to change an existing one.
    The break after this period is whatever gap you leave before the next period's start_time.
    """
    if not (1 <= day_of_week <= 7):
        return {"error": "day_of_week must be 1 (Monday) .. 5 (Friday)"}
    try:
        st, et = _parse_time(start_time), _parse_time(end_time)
    except Exception:
        return {"error": "start_time/end_time must be 'HH:MM', e.g. '08:00'"}
    if et <= st:
        return {"error": "end_time must be after start_time"}
    with get_db() as db:
        _require_member(db, _current_user(db), school_id, admin=True)
        clash = db.query(TimeSlot).filter(
            TimeSlot.school_id == school_id,
            TimeSlot.day_of_week == day_of_week,
            TimeSlot.period_number == period_number,
        ).first()
        if clash:
            return {"error": f"period {period_number} on day {day_of_week} already exists (id {clash.id}); use update_timeslot"}
        ts = TimeSlot(
            school_id=school_id,
            day_of_week=day_of_week,
            period_number=period_number,
            start_time=st,
            end_time=et,
            label=label or None,
        )
        db.add(ts)
        db.commit()
        db.refresh(ts)
        return {
            "id": ts.id, "day_of_week": ts.day_of_week, "period_number": ts.period_number,
            "start_time": _fmt_time(ts.start_time), "end_time": _fmt_time(ts.end_time), "label": ts.label,
        }


@mcp.tool()
def bulk_add_timeslots(school_id: int, slots: list[dict]) -> dict:
    """Add many lektioner at once, e.g. a full week's bell schedule. (Requires admin.)
    slots: list of dicts, each:
      {"day_of_week": int (1-5), "period_number": int, "start_time": "HH:MM", "end_time": "HH:MM", "label": str (optional)}
    Each row is validated independently; rows that are invalid or already exist are reported in "errors".
    Remember: the break after each period is the gap to the next period's start_time the same day.
    """
    created: list[dict] = []
    errors: list[dict] = []
    with get_db() as db:
        _require_member(db, _current_user(db), school_id, admin=True)
        existing = {
            (s.day_of_week, s.period_number)
            for s in db.query(TimeSlot).filter(TimeSlot.school_id == school_id).all()
        }
        for i, s in enumerate(slots):
            try:
                dow = int(s["day_of_week"])
                pn = int(s["period_number"])
                st, et = _parse_time(s["start_time"]), _parse_time(s["end_time"])
            except Exception as e:
                errors.append({"index": i, "error": f"invalid fields: {e}"})
                continue
            if not (1 <= dow <= 7):
                errors.append({"index": i, "error": "day_of_week must be 1 (Monday) .. 5 (Friday)"})
                continue
            if et <= st:
                errors.append({"index": i, "error": "end_time must be after start_time"})
                continue
            if (dow, pn) in existing:
                errors.append({"index": i, "error": f"period {pn} on day {dow} already exists"})
                continue
            ts = TimeSlot(school_id=school_id, day_of_week=dow, period_number=pn, start_time=st, end_time=et, label=(s.get("label") or None))
            db.add(ts)
            db.flush()
            existing.add((dow, pn))
            created.append({"id": ts.id, "day_of_week": dow, "period_number": pn, "start_time": _fmt_time(st), "end_time": _fmt_time(et)})
        db.commit()
    return {"created_count": len(created), "created": created, "errors": errors}


@mcp.tool()
def update_timeslot(school_id: int, slot_id: int, start_time: str = "", end_time: str = "", label: str = "") -> dict:
    """Update a lektion's start_time, end_time and/or label. (Requires admin.) Adjusting the times
    automatically changes the surrounding breaks. Pass times as 'HH:MM'; leave an argument empty ('')
    to keep its current value. To move a slot to a different day/period_number, delete it and add a new one.
    """
    with get_db() as db:
        _require_member(db, _current_user(db), school_id, admin=True)
        ts = db.query(TimeSlot).filter(TimeSlot.id == slot_id, TimeSlot.school_id == school_id).first()
        if not ts:
            return {"error": f"Time slot {slot_id} not found in school {school_id}"}
        try:
            if start_time:
                ts.start_time = _parse_time(start_time)
            if end_time:
                ts.end_time = _parse_time(end_time)
        except Exception:
            return {"error": "start_time/end_time must be 'HH:MM', e.g. '08:00'"}
        if label != "":
            ts.label = label or None
        if ts.end_time <= ts.start_time:
            return {"error": "end_time must be after start_time"}
        db.commit()
        db.refresh(ts)
        return {
            "id": ts.id, "day_of_week": ts.day_of_week, "period_number": ts.period_number,
            "start_time": _fmt_time(ts.start_time), "end_time": _fmt_time(ts.end_time), "label": ts.label,
        }


@mcp.tool()
def delete_timeslot(school_id: int, slot_id: int) -> dict:
    """Delete a lektion (period) from the weekly schedule. (Requires admin.)"""
    with get_db() as db:
        _require_member(db, _current_user(db), school_id, admin=True)
        ts = db.query(TimeSlot).filter(TimeSlot.id == slot_id, TimeSlot.school_id == school_id).first()
        if not ts:
            return {"error": f"Time slot {slot_id} not found in school {school_id}"}
        info = f"day {ts.day_of_week} period {ts.period_number}"
        db.delete(ts)
        db.commit()
        return {"deleted": True, "slot": info}


if __name__ == "__main__":
    # Remote HTTP transport. Auth is enforced by the JWTVerifier above.
    mcp.run(transport="http", host="0.0.0.0", port=8001)

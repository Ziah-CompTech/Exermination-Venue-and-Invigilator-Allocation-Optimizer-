"""
Reusable conflict detection used by:
  - the allocation solver (hard constraints)
  - the manual allocation editor (validation on save)
  - the conflict-resolution page (display)
"""
from datetime import datetime
from typing import Iterable

from ..models.examination import ExaminationSession
from ..models.venue import VenueAllocation, Venue
from ..models.invigilator import InvigilatorAssignment, Invigilator
from ..models.student import StudentSubjectRegistration


# --------------------------------------------------------------------- #
# Time helpers
# --------------------------------------------------------------------- #

def session_interval(s: ExaminationSession):
    return (datetime.combine(s.exam_date, s.start_time),
            datetime.combine(s.exam_date, s.end_time))


def overlaps(a_start: datetime, a_end: datetime,
             b_start: datetime, b_end: datetime) -> bool:
    """Half-open interval overlap: [a_start, a_end) ∩ [b_start, b_end) ≠ ∅."""
    return a_start < b_end and b_start < a_end


def sessions_overlap(a: ExaminationSession, b: ExaminationSession) -> bool:
    a_start, a_end = session_interval(a)
    b_start, b_end = session_interval(b)
    return overlaps(a_start, a_end, b_start, b_end)


# --------------------------------------------------------------------- #
# Venue rules
# --------------------------------------------------------------------- #

def venue_has_capacity(venue: Venue, candidates: int) -> bool:
    return venue.effective_capacity >= candidates


def venue_has_facilities(venue: Venue, required: Iterable[str]) -> bool:
    have = set(venue.facility_list)
    return set(f.lower() for f in required).issubset(have)


def venue_matches_type(venue: Venue, required_type) -> bool:
    return required_type in ("", "any", None) or venue.venue_type == required_type


def venue_is_available(venue: Venue) -> bool:
    return venue.status == "available"


def venue_blocked_at(venue: Venue, start: datetime, end: datetime) -> bool:
    for block in venue.unavailability:
        if overlaps(start, end, block.start_dt, block.end_dt):
            return True
    return False


def venue_double_booked(session: ExaminationSession, venue_id: int) -> bool:
    """True if any OTHER session already uses this venue in an overlapping window."""
    start, end = session_interval(session)
    others = ExaminationSession.query.filter(
        ExaminationSession.id != session.id).all()
    for other in others:
        if other.status == "cancelled":
            continue
        o_start, o_end = session_interval(other)
        if not overlaps(start, end, o_start, o_end):
            continue
        for alloc in other.venue_allocations:
            if alloc.venue_id == venue_id:
                return True
    return False


def venue_eligible_for_session(session: ExaminationSession,
                               venue: Venue):
    """Full eligibility check used for candidate-set filtering."""
    exam = session.examination
    if not venue_is_available(venue):
        return False, f"venue {venue.code} is {venue.status}"
    if not venue_matches_type(venue, exam.required_venue_type):
        return False, f"venue {venue.code} type mismatch"
    if not venue_has_facilities(venue, exam.required_facility_list):
        return False, f"venue {venue.code} lacks required facilities"
    if venue_blocked_at(venue, *session_interval(session)):
        return False, f"venue {venue.code} blocked by unavailability"
    if venue_double_booked(session, venue.id):
        return False, f"venue {venue.code} already booked at overlapping time"
    if venue.effective_capacity <= 0:
        return False, f"venue {venue.code} has zero usable capacity"
    return True, ""


# --------------------------------------------------------------------- #
# Invigilator rules
# --------------------------------------------------------------------- #

def invigilator_teaches_subject(inv: Invigilator, subject_id: int) -> bool:
    return inv.teaches_subject(subject_id)


def invigilator_unavailable(inv: Invigilator, start: datetime,
                            end: datetime) -> bool:
    """
    - No entry for interval → available by default.
    - Explicit 'unavailable' overlap → unavailable.
    - If ANY 'available' windows exist and none cover interval → unavailable.
    """
    windows = list(inv.availability)
    if not windows:
        return False

    for w in windows:
        if not w.is_available and overlaps(start, end, w.start_dt, w.end_dt):
            return True

    has_available_windows = any(w.is_available for w in windows)
    if has_available_windows:
        for w in windows:
            if w.is_available and w.start_dt <= start and w.end_dt >= end:
                return False
        return True

    return False


def invigilator_double_booked(inv_id: int,
                              session: ExaminationSession) -> bool:
    start, end = session_interval(session)
    others = ExaminationSession.query.filter(
        ExaminationSession.id != session.id).all()
    for other in others:
        if other.status == "cancelled":
            continue
        o_start, o_end = session_interval(other)
        if not overlaps(start, end, o_start, o_end):
            continue
        for a in other.invigilator_assignments:
            if a.invigilator_id == inv_id:
                return True
    return False


def invigilator_daily_load(inv_id: int, on_date) -> int:
    total = 0
    for a in InvigilatorAssignment.query.filter_by(
            invigilator_id=inv_id).all():
        if a.session.exam_date == on_date:
            total += 1
    return total


def invigilator_period_load(inv_id: int, exam_period: str) -> int:
    return (InvigilatorAssignment.query
            .join(ExaminationSession)
            .join(ExaminationSession.examination)
            .filter(InvigilatorAssignment.invigilator_id == inv_id,
                    ExaminationSession.examination.has(
                        exam_period=exam_period)).count())


def invigilator_eligible_for_session(inv: Invigilator,
                                     session: ExaminationSession):
    if not inv.is_active:
        return False, "inactive"
    if invigilator_teaches_subject(inv, session.examination.subject_id):
        return False, "teaches subject"
    start, end = session_interval(session)
    if invigilator_unavailable(inv, start, end):
        return False, "unavailable"
    if invigilator_double_booked(inv.id, session):
        return False, "double-booked"
    limit = inv.workload_limit
    if limit:
        if invigilator_daily_load(inv.id,
                                  session.exam_date) >= limit.max_per_day:
            return False, "daily workload limit reached"
        if invigilator_period_load(
                inv.id, session.examination.exam_period
        ) >= limit.max_per_period:
            return False, "period workload limit reached"
    return True, ""


# --------------------------------------------------------------------- #
# Student conflict detection
# --------------------------------------------------------------------- #

def students_in_subject(subject_id: int, exam_period: str | None = None):
    q = StudentSubjectRegistration.query.filter_by(subject_id=subject_id)
    if exam_period:
        q = q.filter_by(exam_period=exam_period)
    return {r.student_id for r in q.all()}


def sessions_share_students(a: ExaminationSession,
                            b: ExaminationSession):
    if a.examination.exam_period != b.examination.exam_period:
        return set()
    if not sessions_overlap(a, b):
        return set()
    sa = students_in_subject(a.examination.subject_id,
                             a.examination.exam_period)
    sb = students_in_subject(b.examination.subject_id,
                             b.examination.exam_period)
    return sa & sb


def detect_all_conflicts() -> dict:
    """Live scan of persisted allocations for hard-constraint violations."""
    result = {
        "venue_over_capacity": [],
        "venue_double_booked": [],
        "invigilator_double_booked": [],
        "invigilator_teaches_subject": [],
        "invigilator_unavailable": [],
        "invigilator_workload_exceeded": [],
        "unallocated_sessions": [],
        "insufficient_invigilators": [],
        "student_conflicts": [],
    }

    all_sessions = ExaminationSession.query.filter(
        ExaminationSession.status != "cancelled").all()

    for s in all_sessions:
        assigned_capacity = sum(va.venue.effective_capacity
                                for va in s.venue_allocations)
        if not s.venue_allocations:
            result["unallocated_sessions"].append(s.id)
        elif assigned_capacity < s.expected_candidates:
            result["venue_over_capacity"].append({
                "session_id": s.id,
                "assigned": assigned_capacity,
                "needed": s.expected_candidates,
            })

        for other in all_sessions:
            if other.id <= s.id:
                continue
            if sessions_overlap(s, other):
                used_a = {va.venue_id for va in s.venue_allocations}
                used_b = {va.venue_id for va in other.venue_allocations}
                clash = used_a & used_b
                if clash:
                    result["venue_double_booked"].append({
                        "a": s.id, "b": other.id, "venues": sorted(clash)
                    })

        for a in s.invigilator_assignments:
            inv = a.invigilator
            if not inv.is_active:
                result["invigilator_unavailable"].append({
                    "session_id": s.id, "invigilator_id": inv.id,
                    "reason": "inactive"
                })
            if inv.teaches_subject(s.examination.subject_id):
                result["invigilator_teaches_subject"].append({
                    "session_id": s.id, "invigilator_id": inv.id,
                    "subject_id": s.examination.subject_id
                })
            start, end = session_interval(s)
            if invigilator_unavailable(inv, start, end):
                result["invigilator_unavailable"].append({
                    "session_id": s.id, "invigilator_id": inv.id,
                    "reason": "unavailable window"
                })
            if invigilator_double_booked(inv.id, s):
                result["invigilator_double_booked"].append({
                    "session_id": s.id, "invigilator_id": inv.id
                })

        if len(s.invigilator_assignments) < s.required_invigilators:
            result["insufficient_invigilators"].append({
                "session_id": s.id,
                "assigned": len(s.invigilator_assignments),
                "required": s.required_invigilators,
            })

    for inv in Invigilator.query.filter_by(is_active=True).all():
        limit = inv.workload_limit
        if not limit:
            continue
        period = None
        for a in inv.assignments:
            period = a.session.examination.exam_period
            break
        if period:
            used = invigilator_period_load(inv.id, period)
            if used > limit.max_per_period:
                result["invigilator_workload_exceeded"].append({
                    "invigilator_id": inv.id, "period": period,
                    "used": used, "limit": limit.max_per_period
                })

    for i, a in enumerate(all_sessions):
        for b in all_sessions[i + 1:]:
            shared = sessions_share_students(a, b)
            if shared:
                result["student_conflicts"].append({
                    "session_a": a.id, "session_b": b.id,
                    "students": sorted(shared)[:10],
                    "total": len(shared)
                })

    return result
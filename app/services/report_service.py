"""
Report data providers. Each function returns a plain list of dicts (or a
dict) that both HTML templates and the CSV/PDF exporters consume.
"""
from datetime import datetime, date
from typing import Optional

from ..models.examination import Examination, ExaminationSession
from ..models.venue import Venue, VenueAllocation
from ..models.invigilator import Invigilator, InvigilatorAssignment
from ..models.student import Student, StudentSubjectRegistration
from ..extensions import db


def _date_filter(query, start, end):
    if start:
        query = query.filter(ExaminationSession.exam_date >= start)
    if end:
        query = query.filter(ExaminationSession.exam_date <= end)
    return query


def list_periods():
    return [p[0] for p in
            db.session.query(Examination.exam_period).distinct().all()]


# --------------------------------------------------------------------- #
# Master timetable
# --------------------------------------------------------------------- #

def master_timetable(period=None, start=None, end=None):
    q = (ExaminationSession.query
         .join(ExaminationSession.examination)
         .filter(ExaminationSession.status.in_(["allocated", "published"])))
    if period:
        q = q.filter(Examination.exam_period == period)
    q = _date_filter(q, start, end)
    q = q.order_by(ExaminationSession.exam_date,
                   ExaminationSession.start_time)
    rows = []
    for s in q.all():
        venues = [va.venue.code for va in s.venue_allocations]
        invs = [a.invigilator.staff_number for a in s.invigilator_assignments]
        rows.append({
            "session_id": s.id,
            "date": s.exam_date,
            "start": s.start_time,
            "end": s.end_time,
            "subject_code": s.examination.subject.code,
            "title": s.examination.title,
            "period": s.examination.exam_period,
            "candidates": s.expected_candidates,
            "venues": ", ".join(venues),
            "invigilators": ", ".join(invs),
        })
    return rows


# --------------------------------------------------------------------- #
# Venue allocation report
# --------------------------------------------------------------------- #

def venue_allocation_report(period=None):
    q = (VenueAllocation.query
         .join(VenueAllocation.session)
         .join(ExaminationSession.examination))
    if period:
        q = q.filter(Examination.exam_period == period)
    q = q.order_by(ExaminationSession.exam_date,
                   ExaminationSession.start_time,
                   Venue.code)
    rows = []
    for va in q.all():
        rows.append({
            "venue_code": va.venue.code,
            "venue_name": va.venue.name,
            "capacity": va.venue.effective_capacity,
            "assigned": va.candidates_assigned,
            "date": va.session.exam_date,
            "start": va.session.start_time,
            "end": va.session.end_time,
            "subject": va.session.examination.subject.code,
            "title": va.session.examination.title,
            "manual": va.is_manual,
        })
    return rows


# --------------------------------------------------------------------- #
# Invigilator duty roster
# --------------------------------------------------------------------- #

def invigilator_roster(period=None, invigilator_id=None):
    q = (InvigilatorAssignment.query
         .join(InvigilatorAssignment.session)
         .join(ExaminationSession.examination)
         .join(Invigilator, InvigilatorAssignment.invigilator_id == Invigilator.id))
    if period:
        q = q.filter(Examination.exam_period == period)
    if invigilator_id:
        q = q.filter(InvigilatorAssignment.invigilator_id == invigilator_id)
    q = q.order_by(Invigilator.staff_number,
                   ExaminationSession.exam_date,
                   ExaminationSession.start_time)
    rows = []
    for a in q.all():
        rows.append({
            "staff_number": a.invigilator.staff_number,
            "name": a.invigilator.full_name,
            "department": (a.invigilator.department.name
                           if a.invigilator.department else ""),
            "date": a.session.exam_date,
            "start": a.session.start_time,
            "end": a.session.end_time,
            "subject": a.session.examination.subject.code,
            "title": a.session.examination.title,
            "venues": ", ".join(va.venue.code
                                for va in a.session.venue_allocations),
            "manual": a.is_manual,
        })
    return rows


# --------------------------------------------------------------------- #
# Student timetable
# --------------------------------------------------------------------- #

def student_timetable(student_id, period=None):
    subject_ids = [r.subject_id for r in
                   StudentSubjectRegistration.query.filter_by(
                       student_id=student_id).all()]
    if not subject_ids:
        return []
    q = (ExaminationSession.query
         .join(ExaminationSession.examination)
         .filter(Examination.subject_id.in_(subject_ids),
                 ExaminationSession.status.in_(["allocated", "published"])))
    if period:
        q = q.filter(Examination.exam_period == period)
    q = q.order_by(ExaminationSession.exam_date,
                   ExaminationSession.start_time)
    rows = []
    for s in q.all():
        rows.append({
            "date": s.exam_date,
            "start": s.start_time,
            "end": s.end_time,
            "subject": s.examination.subject.code,
            "title": s.examination.title,
            "venues": ", ".join(va.venue.code for va in s.venue_allocations),
            "instructions": s.examination.special_requirements or "",
        })
    return rows


# --------------------------------------------------------------------- #
# Venue utilisation
# --------------------------------------------------------------------- #

def venue_utilisation(period=None):
    venues = Venue.query.order_by(Venue.code).all()
    rows = []
    for v in venues:
        q = (VenueAllocation.query
             .filter_by(venue_id=v.id)
             .join(ExaminationSession)
             .join(Examination))
        if period:
            q = q.filter(Examination.exam_period == period)
        allocs = q.all()
        sessions = len(allocs)
        seats_used = sum(a.candidates_assigned for a in allocs)
        capacity_offered = sessions * v.effective_capacity
        pct = (seats_used / capacity_offered * 100) if capacity_offered else 0
        rows.append({
            "venue_code": v.code,
            "venue_name": v.name,
            "capacity": v.effective_capacity,
            "sessions_used": sessions,
            "seats_used": seats_used,
            "utilisation_pct": round(pct, 1),
        })
    return rows


# --------------------------------------------------------------------- #
# Staff workload
# --------------------------------------------------------------------- #

def staff_workload(period=None):
    invs = Invigilator.query.filter_by(is_active=True).order_by(
        Invigilator.staff_number).all()
    rows = []
    for i in invs:
        q = (InvigilatorAssignment.query
             .filter_by(invigilator_id=i.id)
             .join(ExaminationSession)
             .join(Examination))
        if period:
            q = q.filter(Examination.exam_period == period)
        assignments = q.all()
        limit = i.workload_limit
        rows.append({
            "staff_number": i.staff_number,
            "name": i.full_name,
            "department": i.department.name if i.department else "",
            "total": len(assignments),
            "max_per_period": limit.max_per_period if limit else None,
            "max_per_day": limit.max_per_day if limit else None,
        })
    return rows


# --------------------------------------------------------------------- #
# Unallocated sessions
# --------------------------------------------------------------------- #

def unallocated_sessions(period=None):
    q = (ExaminationSession.query
         .join(ExaminationSession.examination)
         .filter(ExaminationSession.status == "unallocated"))
    if period:
        q = q.filter(Examination.exam_period == period)
    rows = []
    for s in q.all():
        rows.append({
            "session_id": s.id,
            "date": s.exam_date,
            "start": s.start_time,
            "end": s.end_time,
            "subject": s.examination.subject.code,
            "title": s.examination.title,
            "period": s.examination.exam_period,
            "candidates": s.expected_candidates,
            "required_invigilators": s.required_invigilators,
        })
    return rows


# --------------------------------------------------------------------- #
# Allocation summary
# --------------------------------------------------------------------- #

def allocation_summary(period=None):
    q = ExaminationSession.query.join(ExaminationSession.examination)
    if period:
        q = q.filter(Examination.exam_period == period)
    sessions = q.all()
    total = len(sessions)
    fully = 0
    capacity_warn = 0
    staff_warn = 0
    for s in sessions:
        seat_cap = sum(va.venue.effective_capacity
                       for va in s.venue_allocations)
        staff_count = len(s.invigilator_assignments)
        if seat_cap >= s.expected_candidates and staff_count >= s.required_invigilators:
            fully += 1
        if seat_cap < s.expected_candidates:
            capacity_warn += 1
        if staff_count < s.required_invigilators:
            staff_warn += 1
    return {
        "period": period or "all",
        "total_sessions": total,
        "fully_allocated": fully,
        "unallocated": total - fully,
        "capacity_warnings": capacity_warn,
        "staffing_warnings": staff_warn,
        "generated_at": datetime.utcnow(),
    }
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import func

from ..extensions import db
from ..models.student import Student
from ..models.examination import Examination, ExaminationSession
from ..models.venue import Venue, VenueAllocation
from ..models.invigilator import Invigilator, InvigilatorAssignment
from ..models.allocation import AllocationRun
from ..models.audit import AuditLog

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    if current_user.role == "invigilator":
        if current_user.invigilator:
            return redirect(url_for("reports.invigilator_schedule",
                                    iid=current_user.invigilator.id))
        return render_template("dashboard/invigilator_home.html")
    if current_user.role == "student":
        if current_user.student:
            return redirect(url_for("reports.student_timetable",
                                    sid=current_user.student.id))
        return render_template("dashboard/student_home.html")

    stats = {
        "students": Student.query.filter_by(is_active=True).count(),
        "examinations": Examination.query.count(),
        "venues": Venue.query.filter_by(status="available").count(),
        "invigilators": Invigilator.query.filter_by(is_active=True).count(),
        "allocated_sessions": ExaminationSession.query.filter_by(
            status="allocated").count(),
        "unallocated_sessions": ExaminationSession.query.filter_by(
            status="unallocated").count(),
        "runs": AllocationRun.query.count(),
        "pending_runs": AllocationRun.query.filter_by(approved=False).count(),
    }

    venue_rows = (db.session.query(
                      Venue.code,
                      func.coalesce(
                          func.sum(VenueAllocation.candidates_assigned), 0))
                  .outerjoin(VenueAllocation,
                             VenueAllocation.venue_id == Venue.id)
                  .group_by(Venue.id)
                  .order_by(func.sum(VenueAllocation.candidates_assigned).desc())
                  .limit(8).all())
    venue_labels = [r[0] for r in venue_rows]
    venue_values = [int(r[1] or 0) for r in venue_rows]

    inv_rows = (db.session.query(
                    Invigilator.staff_number,
                    func.count(InvigilatorAssignment.id))
                .outerjoin(InvigilatorAssignment,
                           InvigilatorAssignment.invigilator_id == Invigilator.id)
                .filter(Invigilator.is_active.is_(True))
                .group_by(Invigilator.id)
                .order_by(func.count(InvigilatorAssignment.id).desc())
                .limit(10).all())
    inv_labels = [r[0] for r in inv_rows]
    inv_values = [int(r[1] or 0) for r in inv_rows]

    recent_logs = AuditLog.query.order_by(
        AuditLog.created_at.desc()).limit(10).all()
    upcoming = ExaminationSession.query.order_by(
        ExaminationSession.exam_date, ExaminationSession.start_time
    ).limit(8).all()

    return render_template(
        "dashboard/index.html",
        stats=stats, recent_logs=recent_logs, upcoming=upcoming,
        venue_labels=venue_labels, venue_values=venue_values,
        inv_labels=inv_labels, inv_values=inv_values,
    )
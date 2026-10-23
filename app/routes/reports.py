from datetime import datetime
from flask import Blueprint, render_template, request, abort, url_for
from flask_login import login_required, current_user

from ..services import report_service as rs
from ..services.export_service import csv_response, pdf_response
from ..models.invigilator import Invigilator
from ..models.student import Student
from ..utils.decorators import role_required

reports_bp = Blueprint("reports", __name__)


def _parse_dates():
    s = request.args.get("start")
    e = request.args.get("end")
    try:
        start = datetime.strptime(s, "%Y-%m-%d").date() if s else None
        end = datetime.strptime(e, "%Y-%m-%d").date() if e else None
    except ValueError:
        start = end = None
    return start, end


@reports_bp.route("/")
@login_required
def index():
    return render_template("reports/index.html", periods=rs.list_periods())


@reports_bp.route("/master-timetable")
@login_required
@role_required("officer")
def master_timetable():
    period = request.args.get("period") or None
    start, end = _parse_dates()
    rows = rs.master_timetable(period, start, end)
    fmt = request.args.get("format")
    if fmt == "csv":
        return csv_response(
            f"master_timetable_{period or 'all'}.csv",
            ["Date", "Start", "End", "Subject", "Title", "Period",
             "Candidates", "Venues", "Invigilators"],
            [[r["date"], r["start"], r["end"], r["subject_code"], r["title"],
              r["period"], r["candidates"], r["venues"], r["invigilators"]]
             for r in rows])
    if fmt == "pdf":
        return pdf_response(
            f"master_timetable_{period or 'all'}.pdf",
            f"Master Examination Timetable — {period or 'All periods'}",
            ["Date", "Time", "Subject", "Title", "Candidates", "Venues",
             "Invigilators"],
            [[r["date"], f"{r['start']}-{r['end']}", r["subject_code"],
              r["title"], r["candidates"], r["venues"], r["invigilators"]]
             for r in rows])
    return render_template("reports/master_timetable.html",
                           rows=rows, period=period,
                           start=start, end=end, periods=rs.list_periods(),
                           generated_at=datetime.utcnow())


@reports_bp.route("/venue-allocation")
@login_required
@role_required("officer")
def venue_allocation():
    period = request.args.get("period") or None
    rows = rs.venue_allocation_report(period)
    fmt = request.args.get("format")
    if fmt == "csv":
        return csv_response(
            f"venue_allocation_{period or 'all'}.csv",
            ["Date", "Start", "End", "Venue", "Name", "Capacity",
             "Assigned", "Subject", "Title", "Manual"],
            [[r["date"], r["start"], r["end"], r["venue_code"],
              r["venue_name"], r["capacity"], r["assigned"],
              r["subject"], r["title"], "yes" if r["manual"] else "no"]
             for r in rows])
    if fmt == "pdf":
        return pdf_response(
            f"venue_allocation_{period or 'all'}.pdf",
            f"Venue Allocation Report — {period or 'All periods'}",
            ["Date", "Time", "Venue", "Capacity", "Assigned", "Subject"],
            [[r["date"], f"{r['start']}-{r['end']}", r["venue_code"],
              r["capacity"], r["assigned"], r["subject"]] for r in rows])
    return render_template("reports/venue_allocation.html",
                           rows=rows, period=period,
                           periods=rs.list_periods(),
                           generated_at=datetime.utcnow())


@reports_bp.route("/invigilator-roster")
@login_required
@role_required("officer")
def invigilator_roster():
    period = request.args.get("period") or None
    rows = rs.invigilator_roster(period)
    fmt = request.args.get("format")
    if fmt == "csv":
        return csv_response(
            f"invigilator_roster_{period or 'all'}.csv",
            ["Staff No", "Name", "Department", "Date", "Start", "End",
             "Subject", "Title", "Venues", "Manual"],
            [[r["staff_number"], r["name"], r["department"], r["date"],
              r["start"], r["end"], r["subject"], r["title"], r["venues"],
              "yes" if r["manual"] else "no"] for r in rows])
    if fmt == "pdf":
        return pdf_response(
            f"invigilator_roster_{period or 'all'}.pdf",
            f"Invigilator Duty Roster — {period or 'All periods'}",
            ["Staff No", "Name", "Date", "Time", "Subject", "Venues"],
            [[r["staff_number"], r["name"], r["date"],
              f"{r['start']}-{r['end']}", r["subject"], r["venues"]]
             for r in rows])
    return render_template("reports/invigilator_roster.html",
                           rows=rows, period=period,
                           periods=rs.list_periods(),
                           generated_at=datetime.utcnow())


@reports_bp.route("/invigilator/<int:iid>")
@login_required
def invigilator_schedule(iid):
    inv = Invigilator.query.get_or_404(iid)
    if current_user.role not in ("admin", "officer") \
            and not (current_user.role == "invigilator"
                     and inv.user_id == current_user.id):
        abort(403)
    period = request.args.get("period") or None
    rows = rs.invigilator_roster(period, invigilator_id=iid)
    fmt = request.args.get("format")
    if fmt == "csv":
        return csv_response(
            f"schedule_{inv.staff_number}_{period or 'all'}.csv",
            ["Date", "Start", "End", "Subject", "Title", "Venues"],
            [[r["date"], r["start"], r["end"], r["subject"], r["title"],
              r["venues"]] for r in rows])
    if fmt == "pdf":
        return pdf_response(
            f"schedule_{inv.staff_number}_{period or 'all'}.pdf",
            f"Invigilation Schedule — {inv.full_name} ({inv.staff_number})",
            ["Date", "Time", "Subject", "Title", "Venue(s)"],
            [[r["date"], f"{r['start']}-{r['end']}", r["subject"],
              r["title"], r["venues"]] for r in rows])
    return render_template("reports/invigilator_schedule.html",
                           inv=inv, rows=rows, period=period,
                           periods=rs.list_periods(),
                           generated_at=datetime.utcnow())


@reports_bp.route("/student/<int:sid>")
@login_required
def student_timetable(sid):
    st = Student.query.get_or_404(sid)
    if current_user.role not in ("admin", "officer") \
            and not (current_user.role == "student"
                     and st.user_id == current_user.id):
        abort(403)
    period = request.args.get("period") or None
    rows = rs.student_timetable(sid, period)
    fmt = request.args.get("format")
    if fmt == "csv":
        return csv_response(
            f"timetable_{st.reg_number}_{period or 'all'}.csv",
            ["Date", "Start", "End", "Subject", "Title", "Venues",
             "Instructions"],
            [[r["date"], r["start"], r["end"], r["subject"], r["title"],
              r["venues"], r["instructions"]] for r in rows])
    if fmt == "pdf":
        return pdf_response(
            f"timetable_{st.reg_number}_{period or 'all'}.pdf",
            f"Student Examination Timetable — {st.full_name} ({st.reg_number})",
            ["Date", "Time", "Subject", "Title", "Venue(s)"],
            [[r["date"], f"{r['start']}-{r['end']}", r["subject"],
              r["title"], r["venues"]] for r in rows],
            landscape_mode=False)
    return render_template("reports/student_timetable.html",
                           st=st, rows=rows, period=period,
                           periods=rs.list_periods(),
                           generated_at=datetime.utcnow())


@reports_bp.route("/my-timetable")
@login_required
def my_timetable():
    if current_user.role == "student" and current_user.student:
        return student_timetable(current_user.student.id)
    if current_user.role == "invigilator" and current_user.invigilator:
        return invigilator_schedule(current_user.invigilator.id)
    return index()


@reports_bp.route("/venue-utilisation")
@login_required
@role_required("officer")
def venue_utilisation():
    period = request.args.get("period") or None
    rows = rs.venue_utilisation(period)
    fmt = request.args.get("format")
    if fmt == "csv":
        return csv_response(
            f"venue_utilisation_{period or 'all'}.csv",
            ["Venue", "Name", "Capacity", "Sessions", "Seats Used",
             "Utilisation %"],
            [[r["venue_code"], r["venue_name"], r["capacity"],
              r["sessions_used"], r["seats_used"], r["utilisation_pct"]]
             for r in rows])
    if fmt == "pdf":
        return pdf_response(
            f"venue_utilisation_{period or 'all'}.pdf",
            f"Venue Utilisation — {period or 'All periods'}",
            ["Venue", "Name", "Capacity", "Sessions", "Seats Used",
             "Utilisation %"],
            [[r["venue_code"], r["venue_name"], r["capacity"],
              r["sessions_used"], r["seats_used"],
              f"{r['utilisation_pct']}%"] for r in rows])
    return render_template("reports/venue_utilisation.html",
                           rows=rows, period=period,
                           periods=rs.list_periods(),
                           generated_at=datetime.utcnow())


@reports_bp.route("/staff-workload")
@login_required
@role_required("officer")
def staff_workload():
    period = request.args.get("period") or None
    rows = rs.staff_workload(period)
    fmt = request.args.get("format")
    if fmt == "csv":
        return csv_response(
            f"staff_workload_{period or 'all'}.csv",
            ["Staff No", "Name", "Department", "Total", "Max/Day",
             "Max/Period"],
            [[r["staff_number"], r["name"], r["department"], r["total"],
              r["max_per_day"] or "", r["max_per_period"] or ""]
             for r in rows])
    if fmt == "pdf":
        return pdf_response(
            f"staff_workload_{period or 'all'}.pdf",
            f"Staff Workload — {period or 'All periods'}",
            ["Staff No", "Name", "Department", "Total"],
            [[r["staff_number"], r["name"], r["department"], r["total"]]
             for r in rows])
    return render_template("reports/staff_workload.html",
                           rows=rows, period=period,
                           periods=rs.list_periods(),
                           generated_at=datetime.utcnow())


@reports_bp.route("/unallocated")
@login_required
@role_required("officer")
def unallocated():
    period = request.args.get("period") or None
    rows = rs.unallocated_sessions(period)
    fmt = request.args.get("format")
    if fmt == "csv":
        return csv_response(
            f"unallocated_{period or 'all'}.csv",
            ["Session", "Date", "Start", "End", "Subject", "Title",
             "Period", "Candidates", "Required Invigilators"],
            [[r["session_id"], r["date"], r["start"], r["end"],
              r["subject"], r["title"], r["period"], r["candidates"],
              r["required_invigilators"]] for r in rows])
    if fmt == "pdf":
        return pdf_response(
            f"unallocated_{period or 'all'}.pdf",
            f"Unallocated Examination Sessions — {period or 'All periods'}",
            ["Session", "Date", "Time", "Subject", "Candidates",
             "Invigilators Needed"],
            [[r["session_id"], r["date"], f"{r['start']}-{r['end']}",
              r["subject"], r["candidates"], r["required_invigilators"]]
             for r in rows])
    return render_template("reports/unallocated.html",
                           rows=rows, period=period,
                           periods=rs.list_periods(),
                           generated_at=datetime.utcnow())


@reports_bp.route("/summary")
@login_required
@role_required("officer")
def summary():
    period = request.args.get("period") or None
    data = rs.allocation_summary(period)
    fmt = request.args.get("format")
    if fmt == "csv":
        return csv_response(
            f"summary_{period or 'all'}.csv",
            ["Metric", "Value"],
            [["Period", data["period"]],
             ["Total sessions", data["total_sessions"]],
             ["Fully allocated", data["fully_allocated"]],
             ["Unallocated", data["unallocated"]],
             ["Capacity warnings", data["capacity_warnings"]],
             ["Staffing warnings", data["staffing_warnings"]],
             ["Generated at",
              data["generated_at"].strftime("%Y-%m-%d %H:%M")]])
    if fmt == "pdf":
        return pdf_response(
            f"summary_{period or 'all'}.pdf",
            f"Allocation Summary — {period or 'All periods'}",
            ["Metric", "Value"],
            [["Total sessions", data["total_sessions"]],
             ["Fully allocated", data["fully_allocated"]],
             ["Unallocated", data["unallocated"]],
             ["Capacity warnings", data["capacity_warnings"]],
             ["Staffing warnings", data["staffing_warnings"]]],
            landscape_mode=False)
    return render_template("reports/summary.html", data=data,
                           period=period, periods=rs.list_periods())


@reports_bp.route("/exceptions")
@login_required
@role_required("officer")
def exceptions():
    from ..services.conflict_detector import detect_all_conflicts
    report = detect_all_conflicts()

    # Pre-format everything as strings for the template
    formatted = {}
    for key, items in report.items():
        lines = []
        for it in items:
            if isinstance(it, dict):
                lines.append(", ".join(f"{k}={v}" for k, v in it.items()))
            else:
                lines.append(str(it))
        formatted[key] = lines

    fmt = request.args.get("format")
    if fmt == "csv":
        flat = [[k, line] for k, lines in formatted.items() for line in lines]
        return csv_response("exceptions.csv", ["Category", "Details"], flat)
    if fmt == "pdf":
        flat = [[k, line] for k, lines in formatted.items() for line in lines]
        return pdf_response("exceptions.pdf",
                            "Conflict & Exception Report",
                            ["Category", "Details"], flat)
    return render_template("reports/exceptions.html", formatted=formatted,
                           generated_at=datetime.utcnow())
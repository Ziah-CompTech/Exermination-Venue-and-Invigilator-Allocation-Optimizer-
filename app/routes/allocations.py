import json
from datetime import datetime
from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request)
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import (StringField, DateField, IntegerField, BooleanField,
                     SubmitField)
from wtforms.validators import DataRequired, Optional, Length, NumberRange

from ..extensions import db
from ..models.examination import Examination, ExaminationSession
from ..models.venue import Venue, VenueAllocation
from ..models.invigilator import Invigilator, InvigilatorAssignment
from ..models.allocation import AllocationRun
from ..models.notification import Notification
from ..models.user import User
from ..services.allocation_solver import run_full_allocation
from ..services.conflict_detector import detect_all_conflicts
from ..services.audit_service import log
from ..utils.decorators import role_required

allocations_bp = Blueprint("allocations", __name__)


class GenerateForm(FlaskForm):
    exam_period = StringField("Exam period",
                              validators=[DataRequired(), Length(2, 32)])
    start_date = DateField("From date (optional)", validators=[Optional()])
    end_date = DateField("To date (optional)", validators=[Optional()])
    max_time = IntegerField("Solver time limit (seconds)",
                            validators=[DataRequired(), NumberRange(5, 300)],
                            default=30)
    allow_under_capacity = BooleanField(
        "Allow under-capacity seating (best-effort)")
    submit = SubmitField("Run Optimiser")


@allocations_bp.route("/")
@login_required
@role_required("officer")
def index():
    runs = (AllocationRun.query
            .order_by(AllocationRun.created_at.desc())
            .limit(50).all())
    return render_template("allocations/index.html", runs=runs)


@allocations_bp.route("/generate", methods=["GET", "POST"])
@login_required
@role_required("officer")
def generate():
    form = GenerateForm()
    if request.method == "GET":
        periods = [p[0] for p in
                   db.session.query(Examination.exam_period).distinct().all()]
        if periods:
            form.exam_period.data = periods[0]

    if form.validate_on_submit():
        period = form.exam_period.data.strip()
        if (form.start_date.data and form.end_date.data
                and form.end_date.data < form.start_date.data):
            flash("End date must be on/after start date.", "danger")
            return render_template("allocations/generate.html", form=form)

        locked = AllocationRun.query.filter_by(
            exam_period=period, approved=True).first()
        if locked:
            flash(f"An approved run already exists for {period}. "
                  f"Unapprove it first.", "danger")
            return render_template("allocations/generate.html", form=form)

        outcome = run_full_allocation(
            exam_period=period,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            max_time_seconds=form.max_time.data,
        )

        try:
            run = AllocationRun(
                exam_period=period,
                start_date=form.start_date.data,
                end_date=form.end_date.data,
                status=outcome.status,
                objective_value=outcome.objective,
                solver_wall_time=outcome.wall_time,
                diagnostics="\n".join(outcome.diagnostics)[:60000],
                parameters=json.dumps({
                    "max_time": form.max_time.data,
                    "allow_under_capacity": form.allow_under_capacity.data,
                }),
                created_by_id=current_user.id,
            )
            db.session.add(run)
            db.session.flush()

            if outcome.status in ("optimal", "feasible"):
                _persist_allocations(run, outcome)
                for sid in outcome.venue_result.assignments:
                    s = ExaminationSession.query.get(sid)
                    if s and len(outcome.venue_result.assignments[sid]) > 0:
                        s.status = "allocated"

            db.session.commit()
            log("run_allocation", "allocation_run", run.id,
                f"period={period} status={outcome.status}")
            _notify_officers(
                title=f"Allocation run #{run.id} finished ({outcome.status})",
                message=f"Period {period}. Wall time {outcome.wall_time:.1f}s.",
                link=url_for("allocations.view", rid=run.id))
            flash(f"Solver finished: {outcome.status.upper()} "
                  f"({outcome.wall_time:.1f}s).",
                  "success" if outcome.status in ("optimal", "feasible")
                  else "warning")
            return redirect(url_for("allocations.view", rid=run.id))
        except Exception as exc:
            db.session.rollback()
            log("run_allocation_failed", "allocation_run", None, str(exc))
            flash(f"Allocation failed: {exc}", "danger")

    return render_template("allocations/generate.html", form=form)


def _persist_allocations(run, outcome):
    for sid in outcome.venue_result.assignments:
        VenueAllocation.query.filter_by(session_id=sid, run_id=None).delete()
        InvigilatorAssignment.query.filter_by(session_id=sid,
                                              run_id=None).delete()

    for sid, venue_map in outcome.venue_result.assignments.items():
        for vid, candidates in venue_map.items():
            db.session.add(VenueAllocation(
                run_id=run.id, session_id=sid, venue_id=vid,
                candidates_assigned=candidates, is_manual=False))

    if outcome.invigilator_result:
        for sid, inv_ids in outcome.invigilator_result.assignments.items():
            for iid in inv_ids:
                db.session.add(InvigilatorAssignment(
                    run_id=run.id, session_id=sid, invigilator_id=iid,
                    is_manual=False))


def _notify_officers(title, message, link=None):
    officers = User.query.filter(
        User.role.in_(["admin", "officer"]),
        User.is_active.is_(True)).all()
    for u in officers:
        db.session.add(Notification(
            user_id=u.id, title=title, message=message,
            category="info", link=link))


@allocations_bp.route("/<int:rid>")
@login_required
@role_required("officer")
def view(rid):
    run = AllocationRun.query.get_or_404(rid)
    sessions = (ExaminationSession.query
                .join(ExaminationSession.examination)
                .filter(ExaminationSession.examination.has(
                    exam_period=run.exam_period)))
    if run.start_date:
        sessions = sessions.filter(
            ExaminationSession.exam_date >= run.start_date)
    if run.end_date:
        sessions = sessions.filter(
            ExaminationSession.exam_date <= run.end_date)
    sessions = sessions.order_by(ExaminationSession.exam_date,
                                 ExaminationSession.start_time).all()

    rows = []
    for s in sessions:
        venue_allocs = VenueAllocation.query.filter_by(
            session_id=s.id, run_id=run.id).all()
        inv_assigns = InvigilatorAssignment.query.filter_by(
            session_id=s.id, run_id=run.id).all()
        total_seats = sum(a.venue.effective_capacity for a in venue_allocs)
        rows.append({
            "session": s,
            "venue_allocs": venue_allocs,
            "invigilator_assigns": inv_assigns,
            "total_seats": total_seats,
            "capacity_ok": total_seats >= s.expected_candidates,
            "staffing_ok": len(inv_assigns) >= s.required_invigilators,
        })

    diagnostics = (run.diagnostics or "").splitlines()
    return render_template("allocations/view.html", run=run, rows=rows,
                           diagnostics=diagnostics)


@allocations_bp.route("/conflicts")
@login_required
@role_required("officer")
def conflicts():
    report = detect_all_conflicts()

    def _session_label(sid):
        s = ExaminationSession.query.get(sid)
        if not s:
            return f"Session {sid}"
        return f"#{s.id} · {s.examination.title} · {s.exam_date} {s.start_time}"

    def _inv_label(iid):
        i = Invigilator.query.get(iid)
        return f"{i.staff_number} — {i.full_name}" if i else f"Invigilator {iid}"

    # Turn every raw report entry into pre-formatted strings
    formatted = {
        "unallocated_sessions": [_session_label(sid)
                                 for sid in report["unallocated_sessions"]],
        "venue_over_capacity": [
            f"{_session_label(it['session_id'])} — assigned "
            f"{it['assigned']} / needed {it['needed']}"
            for it in report["venue_over_capacity"]
        ],
        "venue_double_booked": [
            f"{_session_label(it['a'])} ↔ {_session_label(it['b'])} "
            f"— venues {', '.join(str(v) for v in it['venues'])}"
            for it in report["venue_double_booked"]
        ],
        "invigilator_double_booked": [
            f"{_session_label(it['session_id'])} — {_inv_label(it['invigilator_id'])}"
            for it in report["invigilator_double_booked"]
        ],
        "invigilator_teaches_subject": [
            f"{_session_label(it['session_id'])} — {_inv_label(it['invigilator_id'])}"
            for it in report["invigilator_teaches_subject"]
        ],
        "invigilator_unavailable": [
            f"{_session_label(it['session_id'])} — {_inv_label(it['invigilator_id'])} "
            f"({it['reason']})"
            for it in report["invigilator_unavailable"]
        ],
        "invigilator_workload_exceeded": [
            f"Invigilator #{it['invigilator_id']} — period {it['period']} "
            f"used {it['used']} / limit {it['limit']}"
            for it in report["invigilator_workload_exceeded"]
        ],
        "insufficient_invigilators": [
            f"{_session_label(it['session_id'])} — assigned "
            f"{it['assigned']} / required {it['required']}"
            for it in report["insufficient_invigilators"]
        ],
        "student_conflicts": [
            f"{_session_label(it['session_a'])} ↔ {_session_label(it['session_b'])} "
            f"— {it['total']} student(s)"
            for it in report["student_conflicts"]
        ],
    }

    remedies = _suggest_remedies(report)
    return render_template("allocations/conflicts.html",
                           formatted=formatted, remedies=remedies)


def _suggest_remedies(report):
    suggestions = []
    for sid in report.get("unallocated_sessions", []):
        s = ExaminationSession.query.get(sid)
        if not s:
            continue
        bigger = Venue.query.filter(
            Venue.status == "available",
            Venue.capacity >= s.expected_candidates).order_by(Venue.capacity).first()
        if bigger:
            suggestions.append(
                f"Session #{s.id}: open venue {bigger.code} "
                f"(capacity {bigger.capacity}) to seat {s.expected_candidates}.")
        else:
            suggestions.append(
                f"Session #{s.id}: no single venue seats {s.expected_candidates} "
                f"— split across rooms or reduce candidates.")
    for item in report.get("insufficient_invigilators", []):
        s = ExaminationSession.query.get(item["session_id"])
        if not s:
            continue
        suggestions.append(
            f"Session #{s.id}: add {item['required'] - item['assigned']} eligible "
            f"invigilator(s), or relax workload limits.")
    for item in report.get("venue_over_capacity", []):
        suggestions.append(
            f"Session #{item['session_id']}: capacity {item['assigned']} < "
            f"demand {item['needed']} — assign an additional venue.")
    for item in report.get("invigilator_teaches_subject", []):
        suggestions.append(
            f"Session #{item['session_id']}: invigilator #{item['invigilator_id']} "
            f"teaches this subject — replace.")
    return suggestions


@allocations_bp.route("/<int:rid>/approve", methods=["POST"])
@login_required
@role_required("officer")
def approve(rid):
    run = AllocationRun.query.get_or_404(rid)
    if run.status not in ("optimal", "feasible"):
        flash("Only valid runs can be approved.", "danger")
        return redirect(url_for("allocations.view", rid=rid))
    run.approved = True
    run.approved_at = datetime.utcnow()
    db.session.commit()
    log("approve_allocation", "allocation_run", rid)
    flash("Allocation approved.", "success")
    return redirect(url_for("allocations.view", rid=rid))


@allocations_bp.route("/<int:rid>/unapprove", methods=["POST"])
@login_required
@role_required("officer")
def unapprove(rid):
    run = AllocationRun.query.get_or_404(rid)
    if run.published:
        flash("Unpublish before unapproving.", "danger")
    else:
        run.approved = False
        run.approved_at = None
        db.session.commit()
        log("unapprove_allocation", "allocation_run", rid)
        flash("Approval removed.", "info")
    return redirect(url_for("allocations.view", rid=rid))


@allocations_bp.route("/<int:rid>/publish", methods=["POST"])
@login_required
@role_required("officer")
def publish(rid):
    run = AllocationRun.query.get_or_404(rid)
    if not run.approved:
        flash("Approve the run before publishing.", "danger")
        return redirect(url_for("allocations.view", rid=rid))

    conflicts = detect_all_conflicts()
    hard = (conflicts["venue_over_capacity"]
            + conflicts["venue_double_booked"]
            + conflicts["invigilator_double_booked"]
            + conflicts["invigilator_teaches_subject"]
            + conflicts["insufficient_invigilators"])
    if hard:
        flash(f"Cannot publish — {len(hard)} unresolved conflict(s).", "danger")
        return redirect(url_for("allocations.conflicts"))

    for va in VenueAllocation.query.filter_by(run_id=run.id).all():
        s = va.session
        if s:
            s.status = "published"
    run.published = True
    run.published_at = datetime.utcnow()
    db.session.commit()
    log("publish_allocation", "allocation_run", rid)
    _notify_invigilators_of_run(run)
    flash("Allocation published.", "success")
    return redirect(url_for("allocations.view", rid=rid))


@allocations_bp.route("/<int:rid>/unpublish", methods=["POST"])
@login_required
@role_required("officer")
def unpublish(rid):
    run = AllocationRun.query.get_or_404(rid)
    if not run.published:
        flash("Run is not published.", "info")
    else:
        for va in VenueAllocation.query.filter_by(run_id=run.id).all():
            s = va.session
            if s and s.status == "published":
                s.status = "allocated"
        run.published = False
        run.published_at = None
        db.session.commit()
        log("unpublish_allocation", "allocation_run", rid)
        flash("Run unpublished.", "info")
    return redirect(url_for("allocations.view", rid=rid))


def _notify_invigilators_of_run(run):
    seen = set()
    for a in InvigilatorAssignment.query.filter_by(run_id=run.id).all():
        inv = a.invigilator
        if not inv or not inv.user_id or inv.id in seen:
            continue
        seen.add(inv.id)
        db.session.add(Notification(
            user_id=inv.user_id,
            title="New invigilation duties published",
            message=(f"You have been assigned to session on "
                     f"{a.session.exam_date} at {a.session.start_time}."),
            category="assignment",
        ))
    db.session.commit()
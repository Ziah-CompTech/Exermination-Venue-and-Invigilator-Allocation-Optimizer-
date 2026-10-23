from datetime import datetime, date, time
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from flask_wtf import FlaskForm
from wtforms import (StringField, IntegerField, SelectField, TextAreaField,
                     BooleanField, DateField, TimeField, SubmitField)
from wtforms.validators import DataRequired, Length, Optional, NumberRange

from ..extensions import db
from ..models.examination import Examination, ExaminationSession
from ..models.subject import Subject
from ..services.audit_service import log
from ..utils.decorators import role_required
from ..utils.pagination import paginate, apply_search
from ..utils.validators import overlaps

examinations_bp = Blueprint("examinations", __name__)

VENUE_TYPES = [("any", "Any"), ("lecture_hall", "Lecture Hall"),
               ("lab", "Laboratory"), ("exam_hall", "Examination Hall"),
               ("seminar_room", "Seminar Room"), ("auditorium", "Auditorium")]
STATUSES = [("draft", "Draft"), ("scheduled", "Scheduled"),
            ("allocated", "Allocated"), ("published", "Published"),
            ("cancelled", "Cancelled")]


class ExaminationForm(FlaskForm):
    title = StringField("Examination title",
                        validators=[DataRequired(), Length(3, 180)])
    subject_id = SelectField("Subject", coerce=int,
                             validators=[DataRequired()])
    exam_period = StringField("Exam period",
                              validators=[DataRequired(), Length(2, 32)],
                              default="2025-S1")
    registered_candidates = IntegerField(
        "Registered candidates",
        validators=[DataRequired(), NumberRange(0, 100000)])
    is_estimated = BooleanField("Candidate count is an estimate")
    required_venue_type = SelectField(
        "Required venue type", choices=VENUE_TYPES,
        validators=[DataRequired()])
    required_facilities = StringField(
        "Required facilities (comma separated)",
        validators=[Optional(), Length(max=200)])
    invigilators_required = IntegerField(
        "Invigilators required",
        validators=[DataRequired(), NumberRange(1, 50)], default=1)
    special_requirements = TextAreaField("Special requirements",
                                         validators=[Optional()])
    status = SelectField("Status", choices=STATUSES,
                         validators=[DataRequired()])
    submit = SubmitField("Save")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subject_id.choices = [(s.id, f"{s.code} — {s.title}")
                                   for s in Subject.query.order_by(Subject.code)]


class SessionForm(FlaskForm):
    exam_date = DateField("Date", validators=[DataRequired()])
    start_time = TimeField("Start time", validators=[DataRequired()])
    end_time = TimeField("End time", validators=[DataRequired()])
    expected_candidates = IntegerField(
        "Expected candidates",
        validators=[DataRequired(), NumberRange(1, 100000)])
    required_invigilators = IntegerField(
        "Invigilators required",
        validators=[DataRequired(), NumberRange(1, 50)], default=1)
    submit = SubmitField("Add session")


@examinations_bp.route("/")
@login_required
@role_required("officer")
def index():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    period = request.args.get("period", "").strip()

    query = Examination.query.join(Subject)
    if status:
        query = query.filter(Examination.status == status)
    if period:
        query = query.filter(Examination.exam_period == period)
    if q:
        like = f"%{q}%"
        from sqlalchemy import or_
        query = query.filter(or_(Examination.title.ilike(like),
                                 Subject.code.ilike(like),
                                 Subject.title.ilike(like)))
    query = query.order_by(Examination.created_at.desc())
    page = paginate(query, per_page=15)
    periods = [p[0] for p in
               db.session.query(Examination.exam_period).distinct().all()]
    return render_template("examinations/index.html",
                           page=page, q=q, status=status, period=period,
                           statuses=STATUSES, periods=periods)


@examinations_bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required("officer")
def new():
    form = ExaminationForm()
    if form.validate_on_submit():
        if not Subject.query.get(form.subject_id.data):
            flash("Invalid subject.", "danger")
        else:
            e = Examination(
                title=form.title.data.strip(),
                subject_id=form.subject_id.data,
                exam_period=form.exam_period.data.strip(),
                registered_candidates=form.registered_candidates.data,
                is_estimated=form.is_estimated.data,
                required_venue_type=form.required_venue_type.data,
                required_facilities=form.required_facilities.data or None,
                invigilators_required=form.invigilators_required.data,
                special_requirements=form.special_requirements.data or None,
                status=form.status.data,
            )
            db.session.add(e)
            db.session.commit()
            log("create", "examination", e.id, e.title)
            flash("Examination created. Add sessions to schedule it.",
                  "success")
            return redirect(url_for("examinations.view", eid=e.id))
    return render_template("examinations/form.html", form=form,
                           title="New Examination")


@examinations_bp.route("/<int:eid>/edit", methods=["GET", "POST"])
@login_required
@role_required("officer")
def edit(eid):
    e = Examination.query.get_or_404(eid)
    if e.status == "published":
        flash("Published examinations cannot be edited. Unpublish first.",
              "danger")
        return redirect(url_for("examinations.view", eid=e.id))

    form = ExaminationForm(obj=e)
    if form.validate_on_submit():
        e.title = form.title.data.strip()
        e.subject_id = form.subject_id.data
        e.exam_period = form.exam_period.data.strip()
        e.registered_candidates = form.registered_candidates.data
        e.is_estimated = form.is_estimated.data
        e.required_venue_type = form.required_venue_type.data
        e.required_facilities = form.required_facilities.data or None
        e.invigilators_required = form.invigilators_required.data
        e.special_requirements = form.special_requirements.data or None
        e.status = form.status.data
        db.session.commit()
        log("update", "examination", e.id)
        flash("Examination updated.", "success")
        return redirect(url_for("examinations.view", eid=e.id))
    return render_template("examinations/form.html", form=form,
                           title=f"Edit {e.title}")


@examinations_bp.route("/<int:eid>")
@login_required
@role_required("officer")
def view(eid):
    e = Examination.query.get_or_404(eid)
    return render_template("examinations/view.html", e=e)


@examinations_bp.route("/<int:eid>/sessions", methods=["GET", "POST"])
@login_required
@role_required("officer")
def sessions(eid):
    e = Examination.query.get_or_404(eid)
    if e.status == "published":
        flash("Published examinations cannot be modified.", "danger")
        return redirect(url_for("examinations.view", eid=e.id))

    form = SessionForm()
    if form.validate_on_submit():
        if form.end_time.data <= form.start_time.data:
            flash("End time must be after start time.", "danger")
        else:
            start = form.start_time.data
            end = form.end_time.data
            clash = next(
                (s for s in e.sessions
                 if s.exam_date == form.exam_date.data
                 and overlaps(start, end, s.start_time, s.end_time)),
                None)
            if clash:
                flash(f"Overlaps with existing session "
                      f"{clash.start_time}-{clash.end_time}.", "danger")
            else:
                s = ExaminationSession(
                    examination_id=e.id,
                    exam_date=form.exam_date.data,
                    start_time=start, end_time=end,
                    expected_candidates=form.expected_candidates.data,
                    required_invigilators=form.required_invigilators.data,
                )
                db.session.add(s)
                db.session.commit()
                log("create", "examination_session", s.id)
                flash("Session added.", "success")
                return redirect(url_for("examinations.sessions", eid=e.id))

    return render_template("examinations/sessions.html", e=e, form=form)


@examinations_bp.route("/sessions/<int:sid>/delete", methods=["POST"])
@login_required
@role_required("officer")
def delete_session(sid):
    s = ExaminationSession.query.get_or_404(sid)
    if s.status == "published" or s.examination.status == "published":
        flash("Cannot delete a published session.", "danger")
        return redirect(url_for("examinations.sessions",
                                eid=s.examination_id))
    eid = s.examination_id
    db.session.delete(s)
    db.session.commit()
    log("delete", "examination_session", sid)
    flash("Session deleted.", "success")
    return redirect(url_for("examinations.sessions", eid=eid))


@examinations_bp.route("/<int:eid>/delete", methods=["POST"])
@login_required
@role_required("officer")
def delete(eid):
    e = Examination.query.get_or_404(eid)
    if e.status == "published":
        flash("Cannot delete a published examination.", "danger")
        return redirect(url_for("examinations.view", eid=e.id))
    title = e.title
    db.session.delete(e)
    db.session.commit()
    log("delete", "examination", eid, title)
    flash("Examination deleted.", "success")
    return redirect(url_for("examinations.index"))
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from flask_wtf import FlaskForm
from wtforms import (StringField, SelectField, BooleanField, TextAreaField,
                     IntegerField, DateTimeLocalField, SubmitField,
                     SelectMultipleField)
from wtforms.validators import DataRequired, Length, Optional, Email, NumberRange

from ..extensions import db
from ..models.invigilator import (Invigilator, InvigilatorSubject,
                                  InvigilatorAvailability,
                                  InvigilatorWorkloadLimit)
from ..models.subject import Department, Subject
from ..models.user import User
from ..services.audit_service import log
from ..utils.decorators import role_required
from ..utils.pagination import paginate, apply_search

invigilators_bp = Blueprint("invigilators", __name__)


class InvigilatorForm(FlaskForm):
    staff_number = StringField("Staff number",
                               validators=[DataRequired(), Length(2, 32)])
    full_name = StringField("Full name",
                            validators=[DataRequired(), Length(3, 120)])
    email = StringField("Email", validators=[Optional(), Email()])
    phone = StringField("Phone", validators=[Optional(), Length(max=32)])
    department_id = SelectField("Department", coerce=int,
                                validators=[Optional()])
    user_id = SelectField("Linked user account", coerce=int,
                          validators=[Optional()])
    is_active = BooleanField("Active", default=True)
    is_external = BooleanField("External")
    notes = TextAreaField("Notes", validators=[Optional()])
    subjects_taught = SelectMultipleField("Subjects taught", coerce=int)
    submit = SubmitField("Save")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.department_id.choices = [(0, "— none —")] + [
            (d.id, f"{d.code} — {d.name}")
            for d in Department.query.order_by(Department.name)
        ]
        self.user_id.choices = [(0, "— none —")] + [
            (u.id, f"{u.username} ({u.role})")
            for u in User.query.filter(
                User.role.in_(["invigilator", "officer", "admin"]))
                .order_by(User.username)
        ]
        self.subjects_taught.choices = [
            (s.id, f"{s.code} — {s.title}")
            for s in Subject.query.order_by(Subject.code)
        ]


class AvailabilityForm(FlaskForm):
    start_dt = DateTimeLocalField("From", format="%Y-%m-%dT%H:%M",
                                  validators=[DataRequired()])
    end_dt = DateTimeLocalField("To", format="%Y-%m-%dT%H:%M",
                                validators=[DataRequired()])
    is_available = SelectField(
        "Type",
        choices=[("1", "Available"), ("0", "Unavailable")],
        default="1")
    reason = StringField("Reason", validators=[Optional(), Length(max=200)])
    submit = SubmitField("Add")


class WorkloadForm(FlaskForm):
    max_per_day = IntegerField(
        "Max duties per day",
        validators=[DataRequired(), NumberRange(1, 20)], default=2)
    max_per_period = IntegerField(
        "Max duties per exam period",
        validators=[DataRequired(), NumberRange(1, 100)], default=10)
    submit = SubmitField("Save")


@invigilators_bp.route("/")
@login_required
@role_required("officer")
def index():
    q = request.args.get("q", "").strip()
    query = Invigilator.query
    query = apply_search(query, Invigilator, q,
                         ["staff_number", "full_name", "email"])
    query = query.order_by(Invigilator.staff_number)
    page = paginate(query, per_page=20)
    return render_template("invigilators/index.html", page=page, q=q)


def _populate(record: Invigilator, form: InvigilatorForm):
    record.staff_number = form.staff_number.data
    record.full_name = form.full_name.data
    record.email = form.email.data or None
    record.phone = form.phone.data or None
    record.department_id = form.department_id.data or None
    record.user_id = form.user_id.data or None
    record.is_active = form.is_active.data
    record.is_external = form.is_external.data
    record.notes = form.notes.data or None

    selected = set(form.subjects_taught.data or [])
    existing = {s.subject_id for s in record.subjects_taught}
    for sid in selected - existing:
        db.session.add(InvigilatorSubject(invigilator=record, subject_id=sid))
    for sid in existing - selected:
        InvigilatorSubject.query.filter_by(
            invigilator_id=record.id, subject_id=sid).delete()


@invigilators_bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required("officer")
def new():
    form = InvigilatorForm()
    if form.validate_on_submit():
        if not (form.staff_number.data or "").strip() or \
           not (form.full_name.data or "").strip():
            flash("Staff number and full name are required.", "danger")
            return render_template("invigilators/form.html", form=form,
                                   title="New Invigilator")

        if Invigilator.query.filter_by(
                staff_number=form.staff_number.data.strip()).first():
            flash("Staff number already exists.", "danger")
        else:
            i = Invigilator()
            _populate(i, form)
            db.session.add(i)
            db.session.flush()
            db.session.add(InvigilatorWorkloadLimit(
                invigilator_id=i.id, max_per_day=2, max_per_period=10))
            db.session.commit()
            log("create", "invigilator", i.id, i.staff_number)
            flash("Invigilator created.", "success")
            return redirect(url_for("invigilators.index"))
    return render_template("invigilators/form.html", form=form,
                           title="New Invigilator")


@invigilators_bp.route("/<int:iid>/edit", methods=["GET", "POST"])
@login_required
@role_required("officer")
def edit(iid):
    i = Invigilator.query.get_or_404(iid)
    form = InvigilatorForm(obj=i)
    if request.method == "GET":
        form.subjects_taught.data = [s.subject_id for s in i.subjects_taught]
        form.department_id.data = i.department_id or 0
        form.user_id.data = i.user_id or 0

    if form.validate_on_submit():
        clash = Invigilator.query.filter(
            Invigilator.staff_number == form.staff_number.data,
            Invigilator.id != i.id).first()
        if clash:
            flash("Staff number already exists.", "danger")
        else:
            _populate(i, form)
            db.session.commit()
            log("update", "invigilator", i.id)
            flash("Invigilator updated.", "success")
            return redirect(url_for("invigilators.index"))
    return render_template("invigilators/form.html", form=form,
                           title=f"Edit {i.staff_number}")


@invigilators_bp.route("/<int:iid>")
@login_required
@role_required("officer")
def view(iid):
    i = Invigilator.query.get_or_404(iid)
    return render_template("invigilators/view.html", i=i)


@invigilators_bp.route("/<int:iid>/availability", methods=["GET", "POST"])
@login_required
@role_required("officer")
def availability(iid):
    i = Invigilator.query.get_or_404(iid)
    form = AvailabilityForm()
    if form.validate_on_submit():
        if form.end_dt.data <= form.start_dt.data:
            flash("End must be after start.", "danger")
        else:
            a = InvigilatorAvailability(
                invigilator_id=i.id,
                start_dt=form.start_dt.data,
                end_dt=form.end_dt.data,
                is_available=(form.is_available.data == "1"),
                reason=form.reason.data or None,
            )
            db.session.add(a)
            db.session.commit()
            log("create", "invigilator_availability", a.id)
            flash("Availability entry added.", "success")
            return redirect(url_for("invigilators.availability", iid=i.id))
    items = (InvigilatorAvailability.query
             .filter_by(invigilator_id=i.id)
             .order_by(InvigilatorAvailability.start_dt.desc()).all())
    return render_template("invigilators/availability.html",
                           i=i, form=form, items=items)


@invigilators_bp.route("/availability/<int:aid>/delete", methods=["POST"])
@login_required
@role_required("officer")
def delete_availability(aid):
    a = InvigilatorAvailability.query.get_or_404(aid)
    iid = a.invigilator_id
    db.session.delete(a)
    db.session.commit()
    log("delete", "invigilator_availability", aid)
    flash("Entry removed.", "success")
    return redirect(url_for("invigilators.availability", iid=iid))


@invigilators_bp.route("/<int:iid>/workload", methods=["GET", "POST"])
@login_required
@role_required("officer")
def workload(iid):
    i = Invigilator.query.get_or_404(iid)
    limit = i.workload_limit
    if not limit:
        limit = InvigilatorWorkloadLimit(
            invigilator_id=i.id, max_per_day=2, max_per_period=10)
        db.session.add(limit)
        db.session.commit()
    form = WorkloadForm(obj=limit)
    if form.validate_on_submit():
        limit.max_per_day = form.max_per_day.data
        limit.max_per_period = form.max_per_period.data
        db.session.commit()
        log("update", "invigilator_workload", limit.id)
        flash("Workload limits updated.", "success")
        return redirect(url_for("invigilators.view", iid=i.id))
    return render_template("invigilators/workload.html",
                           i=i, form=form, limit=limit)
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from flask_wtf import FlaskForm
from wtforms import (StringField, IntegerField, SelectField, BooleanField,
                     TextAreaField, DateTimeLocalField, SubmitField)
from wtforms.validators import DataRequired, Length, Optional, NumberRange

from ..extensions import db
from ..models.venue import Venue, VenueAvailability
from ..services.audit_service import log
from ..utils.decorators import role_required
from ..utils.pagination import paginate, apply_search

venues_bp = Blueprint("venues", __name__)

VENUE_TYPES = [("lecture_hall", "Lecture Hall"), ("lab", "Laboratory"),
               ("exam_hall", "Examination Hall"), ("seminar_room", "Seminar Room"),
               ("auditorium", "Auditorium")]
STATUSES = [("available", "Available"), ("maintenance", "Maintenance"),
            ("closed", "Closed")]


class VenueForm(FlaskForm):
    code = StringField("Venue code", validators=[DataRequired(), Length(2, 32)])
    name = StringField("Name", validators=[DataRequired(), Length(3, 120)])
    building = StringField("Building", validators=[Optional(), Length(max=120)])
    location = StringField("Location", validators=[Optional(), Length(max=120)])
    capacity = IntegerField("Capacity",
                            validators=[DataRequired(), NumberRange(1, 10000)])
    usable_capacity = IntegerField("Usable capacity",
                                   validators=[Optional(), NumberRange(1, 10000)])
    venue_type = SelectField("Type", choices=VENUE_TYPES,
                             validators=[DataRequired()])
    facilities = StringField("Facilities (comma separated)",
                             validators=[Optional(), Length(max=200)])
    is_accessible = BooleanField("Wheelchair accessible")
    accessibility_notes = TextAreaField("Accessibility notes",
                                        validators=[Optional()])
    status = SelectField("Status", choices=STATUSES,
                         validators=[DataRequired()])
    submit = SubmitField("Save")


class AvailabilityForm(FlaskForm):
    start_dt = DateTimeLocalField("From", format="%Y-%m-%dT%H:%M",
                                  validators=[DataRequired()])
    end_dt = DateTimeLocalField("To", format="%Y-%m-%dT%H:%M",
                                validators=[DataRequired()])
    reason = StringField("Reason", validators=[Optional(), Length(max=200)])
    submit = SubmitField("Add Block")


@venues_bp.route("/")
@login_required
@role_required("officer")
def index():
    q = request.args.get("q", "").strip()
    vtype = request.args.get("type", "").strip()
    query = Venue.query
    if vtype:
        query = query.filter_by(venue_type=vtype)
    query = apply_search(query, Venue, q,
                         ["code", "name", "building", "location"])
    query = query.order_by(Venue.code)
    page = paginate(query, per_page=20)
    return render_template("venues/index.html", page=page, q=q, vtype=vtype,
                           venue_types=VENUE_TYPES)


@venues_bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required("officer")
def new():
    form = VenueForm()
    if form.validate_on_submit():
        if Venue.query.filter_by(code=form.code.data.upper()).first():
            flash("Venue code already exists.", "danger")
        elif (form.usable_capacity.data
              and form.usable_capacity.data > form.capacity.data):
            flash("Usable capacity cannot exceed total capacity.", "danger")
        else:
            v = Venue(
                code=form.code.data.upper(),
                name=form.name.data,
                building=form.building.data or None,
                location=form.location.data or None,
                capacity=form.capacity.data,
                usable_capacity=form.usable_capacity.data,
                venue_type=form.venue_type.data,
                facilities=form.facilities.data or None,
                is_accessible=form.is_accessible.data,
                accessibility_notes=form.accessibility_notes.data or None,
                status=form.status.data,
            )
            db.session.add(v)
            db.session.commit()
            log("create", "venue", v.id, v.code)
            flash("Venue created.", "success")
            return redirect(url_for("venues.index"))
    return render_template("venues/form.html", form=form, title="New Venue")


@venues_bp.route("/<int:vid>/edit", methods=["GET", "POST"])
@login_required
@role_required("officer")
def edit(vid):
    v = Venue.query.get_or_404(vid)
    form = VenueForm(obj=v)
    if form.validate_on_submit():
        clash = Venue.query.filter(
            Venue.code == form.code.data.upper(),
            Venue.id != v.id).first()
        if clash:
            flash("Venue code already exists.", "danger")
        elif (form.usable_capacity.data
              and form.usable_capacity.data > form.capacity.data):
            flash("Usable capacity cannot exceed total capacity.", "danger")
        else:
            v.code = form.code.data.upper()
            v.name = form.name.data
            v.building = form.building.data or None
            v.location = form.location.data or None
            v.capacity = form.capacity.data
            v.usable_capacity = form.usable_capacity.data
            v.venue_type = form.venue_type.data
            v.facilities = form.facilities.data or None
            v.is_accessible = form.is_accessible.data
            v.accessibility_notes = form.accessibility_notes.data or None
            v.status = form.status.data
            db.session.commit()
            log("update", "venue", v.id)
            flash("Venue updated.", "success")
            return redirect(url_for("venues.index"))
    return render_template("venues/form.html", form=form,
                           title=f"Edit {v.code}")


@venues_bp.route("/<int:vid>/availability", methods=["GET", "POST"])
@login_required
@role_required("officer")
def availability(vid):
    v = Venue.query.get_or_404(vid)
    form = AvailabilityForm()
    if form.validate_on_submit():
        if form.end_dt.data <= form.start_dt.data:
            flash("End must be after start.", "danger")
        else:
            a = VenueAvailability(
                venue_id=v.id,
                start_dt=form.start_dt.data,
                end_dt=form.end_dt.data,
                reason=form.reason.data or None,
            )
            db.session.add(a)
            db.session.commit()
            log("create", "venue_availability", a.id, f"venue={v.code}")
            flash("Unavailability period added.", "success")
            return redirect(url_for("venues.availability", vid=v.id))
    blocks = (VenueAvailability.query.filter_by(venue_id=v.id)
              .order_by(VenueAvailability.start_dt.desc()).all())
    return render_template("venues/availability.html", v=v, form=form,
                           blocks=blocks)


@venues_bp.route("/availability/<int:aid>/delete", methods=["POST"])
@login_required
@role_required("officer")
def delete_availability(aid):
    a = VenueAvailability.query.get_or_404(aid)
    vid = a.venue_id
    db.session.delete(a)
    db.session.commit()
    log("delete", "venue_availability", aid)
    flash("Unavailability period removed.", "success")
    return redirect(url_for("venues.availability", vid=vid))
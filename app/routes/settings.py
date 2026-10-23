from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange

from ..extensions import db
from ..models.allocation import InstitutionSettings
from ..services.audit_service import log
from ..utils.decorators import role_required

settings_bp = Blueprint("settings", __name__)


class SettingsForm(FlaskForm):
    institution_name = StringField(
        "Institution name",
        validators=[DataRequired(), Length(3, 180)])
    default_safety_margin = IntegerField(
        "Default safety margin (seats)",
        validators=[DataRequired(), NumberRange(0, 500)], default=0)
    solver_max_time_seconds = IntegerField(
        "Solver time limit (seconds)",
        validators=[DataRequired(), NumberRange(5, 600)], default=30)
    default_invigilators_per_session = IntegerField(
        "Default invigilators per session",
        validators=[DataRequired(), NumberRange(1, 20)], default=1)
    default_max_duties_per_day = IntegerField(
        "Default max duties per invigilator per day",
        validators=[DataRequired(), NumberRange(1, 20)], default=2)
    default_max_duties_per_period = IntegerField(
        "Default max duties per invigilator per period",
        validators=[DataRequired(), NumberRange(1, 200)], default=10)
    submit = SubmitField("Save settings")


@settings_bp.route("/", methods=["GET", "POST"])
@login_required
@role_required("admin")
def index():
    s = InstitutionSettings.get()
    form = SettingsForm(obj=s)
    if form.validate_on_submit():
        s.institution_name = form.institution_name.data.strip()
        s.default_safety_margin = form.default_safety_margin.data
        s.solver_max_time_seconds = form.solver_max_time_seconds.data
        s.default_invigilators_per_session = \
            form.default_invigilators_per_session.data
        s.default_max_duties_per_day = form.default_max_duties_per_day.data
        s.default_max_duties_per_period = \
            form.default_max_duties_per_period.data
        db.session.commit()
        log("update", "settings", s.id)
        flash("Settings saved.", "success")
        return redirect(url_for("settings.index"))
    return render_template("settings/index.html", form=form, s=s)
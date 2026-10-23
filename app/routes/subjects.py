from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, NumberRange

from ..extensions import db
from ..models.subject import Subject, Department
from ..services.audit_service import log
from ..utils.decorators import role_required
from ..utils.pagination import paginate, apply_search

subjects_bp = Blueprint("subjects", __name__)


class SubjectForm(FlaskForm):
    code = StringField("Subject code", validators=[DataRequired(), Length(2, 20)])
    title = StringField("Title", validators=[DataRequired(), Length(3, 150)])
    credit_hours = IntegerField(
        "Credit hours",
        validators=[DataRequired(), NumberRange(1, 12)], default=3)
    department_id = SelectField("Department", coerce=int, validators=[Optional()])
    submit = SubmitField("Save")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.department_id.choices = [(0, "— none —")] + [
            (d.id, f"{d.code} — {d.name}")
            for d in Department.query.order_by(Department.name)
        ]


class DepartmentForm(FlaskForm):
    code = StringField("Code", validators=[DataRequired(), Length(2, 20)])
    name = StringField("Name", validators=[DataRequired(), Length(3, 120)])
    submit = SubmitField("Save")


@subjects_bp.route("/")
@login_required
@role_required("officer")
def index():
    q = request.args.get("q", "").strip()
    query = Subject.query
    query = apply_search(query, Subject, q, ["code", "title"])
    query = query.order_by(Subject.code)
    page = paginate(query, per_page=20)
    return render_template("subjects/index.html", page=page, q=q)


@subjects_bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required("officer")
def new():
    form = SubjectForm()
    if form.validate_on_submit():
        if Subject.query.filter_by(code=form.code.data.upper()).first():
            flash("Subject code already exists.", "danger")
        else:
            s = Subject(
                code=form.code.data.upper(),
                title=form.title.data,
                credit_hours=form.credit_hours.data,
                department_id=form.department_id.data or None,
            )
            db.session.add(s)
            db.session.commit()
            log("create", "subject", s.id, s.code)
            flash("Subject created.", "success")
            return redirect(url_for("subjects.index"))
    return render_template("subjects/form.html", form=form, title="New Subject")


@subjects_bp.route("/<int:sid>/edit", methods=["GET", "POST"])
@login_required
@role_required("officer")
def edit(sid):
    s = Subject.query.get_or_404(sid)
    form = SubjectForm(obj=s)
    if form.validate_on_submit():
        clash = Subject.query.filter(
            Subject.code == form.code.data.upper(),
            Subject.id != s.id).first()
        if clash:
            flash("Subject code already exists.", "danger")
        else:
            s.code = form.code.data.upper()
            s.title = form.title.data
            s.credit_hours = form.credit_hours.data
            s.department_id = form.department_id.data or None
            db.session.commit()
            log("update", "subject", s.id)
            flash("Subject updated.", "success")
            return redirect(url_for("subjects.index"))
    return render_template("subjects/form.html", form=form,
                           title=f"Edit {s.code}")


@subjects_bp.route("/<int:sid>/delete", methods=["POST"])
@login_required
@role_required("officer")
def delete(sid):
    s = Subject.query.get_or_404(sid)
    if s.examinations:
        flash("Cannot delete: subject has examinations.", "danger")
    else:
        db.session.delete(s)
        db.session.commit()
        log("delete", "subject", sid)
        flash("Subject deleted.", "success")
    return redirect(url_for("subjects.index"))


# --------------------------------------------------------------------- #
# Departments
# --------------------------------------------------------------------- #

@subjects_bp.route("/departments")
@login_required
@role_required("officer")
def departments():
    items = Department.query.order_by(Department.name).all()
    return render_template("subjects/departments.html", items=items)


@subjects_bp.route("/departments/new", methods=["GET", "POST"])
@login_required
@role_required("officer")
def department_new():
    form = DepartmentForm()
    if form.validate_on_submit():
        if Department.query.filter_by(code=form.code.data.upper()).first():
            flash("Department code already exists.", "danger")
        else:
            d = Department(code=form.code.data.upper(), name=form.name.data)
            db.session.add(d)
            db.session.commit()
            log("create", "department", d.id, d.code)
            flash("Department created.", "success")
            return redirect(url_for("subjects.departments"))
    return render_template("subjects/department_form.html", form=form,
                           title="New Department")


@subjects_bp.route("/departments/<int:did>/edit", methods=["GET", "POST"])
@login_required
@role_required("officer")
def department_edit(did):
    d = Department.query.get_or_404(did)
    form = DepartmentForm(obj=d)
    if form.validate_on_submit():
        d.code = form.code.data.upper()
        d.name = form.name.data
        db.session.commit()
        log("update", "department", d.id)
        flash("Department updated.", "success")
        return redirect(url_for("subjects.departments"))
    return render_template("subjects/department_form.html", form=form,
                           title=f"Edit {d.code}")
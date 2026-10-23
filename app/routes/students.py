import csv
import io
from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, Response)
from flask_login import login_required
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (StringField, SelectField, IntegerField, BooleanField,
                     SubmitField)
from wtforms.validators import DataRequired, Length, Optional, Email, NumberRange

from ..extensions import db
from ..models.student import Student
from ..models.subject import Department, Subject
from ..models.user import User
from ..services.audit_service import log
from ..utils.decorators import role_required
from ..utils.pagination import paginate, apply_search

students_bp = Blueprint("students", __name__)


class StudentForm(FlaskForm):
    reg_number = StringField("Registration number",
                             validators=[DataRequired(), Length(2, 32)])
    full_name = StringField("Full name",
                            validators=[DataRequired(), Length(3, 120)])
    email = StringField("Email", validators=[Optional(), Email()])
    phone = StringField("Phone", validators=[Optional(), Length(max=32)])
    year_of_study = IntegerField(
        "Year of study",
        validators=[DataRequired(), NumberRange(1, 10)], default=1)
    programme = StringField("Programme",
                            validators=[Optional(), Length(max=120)])
    department_id = SelectField("Department", coerce=int,
                                validators=[Optional()])
    user_id = SelectField("Linked user account", coerce=int,
                          validators=[Optional()])
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.department_id.choices = [(0, "— none —")] + [
            (d.id, f"{d.code} — {d.name}")
            for d in Department.query.order_by(Department.name)
        ]
        self.user_id.choices = [(0, "— none —")] + [
            (u.id, f"{u.username} ({u.email})")
            for u in User.query.filter_by(role="student")
                                .order_by(User.username)
        ]


class ImportForm(FlaskForm):
    file = FileField("CSV file",
                     validators=[DataRequired(),
                                 FileAllowed(["csv"], "CSV only.")])
    submit = SubmitField("Import")


@students_bp.route("/")
@login_required
@role_required("officer")
def index():
    q = request.args.get("q", "").strip()
    query = Student.query
    query = apply_search(query, Student, q,
                         ["reg_number", "full_name", "programme", "email"])
    query = query.order_by(Student.reg_number)
    page = paginate(query, per_page=20)
    return render_template("students/index.html", page=page, q=q)


@students_bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required("officer")
def new():
    form = StudentForm()
    if form.validate_on_submit():
        if Student.query.filter_by(reg_number=form.reg_number.data).first():
            flash("Registration number already exists.", "danger")
        else:
            s = Student(
                reg_number=form.reg_number.data,
                full_name=form.full_name.data,
                email=form.email.data or None,
                phone=form.phone.data or None,
                year_of_study=form.year_of_study.data,
                programme=form.programme.data or None,
                department_id=form.department_id.data or None,
                user_id=form.user_id.data or None,
                is_active=form.is_active.data,
            )
            db.session.add(s)
            db.session.commit()
            log("create", "student", s.id, s.reg_number)
            flash("Student created.", "success")
            return redirect(url_for("students.index"))
    return render_template("students/form.html", form=form,
                           title="New Student")


@students_bp.route("/<int:sid>/edit", methods=["GET", "POST"])
@login_required
@role_required("officer")
def edit(sid):
    s = Student.query.get_or_404(sid)
    form = StudentForm(obj=s)
    if form.validate_on_submit():
        clash = Student.query.filter(Student.reg_number == form.reg_number.data,
                                     Student.id != s.id).first()
        if clash:
            flash("Registration number already exists.", "danger")
        else:
            s.reg_number = form.reg_number.data
            s.full_name = form.full_name.data
            s.email = form.email.data or None
            s.phone = form.phone.data or None
            s.year_of_study = form.year_of_study.data
            s.programme = form.programme.data or None
            s.department_id = form.department_id.data or None
            s.user_id = form.user_id.data or None
            s.is_active = form.is_active.data
            db.session.commit()
            log("update", "student", s.id)
            flash("Student updated.", "success")
            return redirect(url_for("students.index"))
    return render_template("students/form.html", form=form,
                           title=f"Edit {s.reg_number}")


@students_bp.route("/<int:sid>")
@login_required
@role_required("officer")
def view(sid):
    s = Student.query.get_or_404(sid)
    return render_template("students/view.html", s=s)


@students_bp.route("/<int:sid>/deactivate", methods=["POST"])
@login_required
@role_required("officer")
def deactivate(sid):
    s = Student.query.get_or_404(sid)
    s.is_active = not s.is_active
    db.session.commit()
    log("toggle_active", "student", s.id, f"active={s.is_active}")
    flash("Student status changed.", "success")
    return redirect(url_for("students.index"))


@students_bp.route("/import", methods=["GET", "POST"])
@login_required
@role_required("officer")
def import_csv():
    form = ImportForm()
    summary = None
    if form.validate_on_submit():
        raw = form.file.data.read().decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(raw))
        required = {"reg_number", "full_name"}
        if not required.issubset({c.strip() for c in (reader.fieldnames or [])}):
            flash("CSV must have columns: reg_number, full_name "
                  "(email, phone, year_of_study, programme, "
                  "department_code optional).", "danger")
        else:
            created, skipped, errors = 0, 0, []
            for i, row in enumerate(reader, start=2):
                reg = (row.get("reg_number") or "").strip()
                name = (row.get("full_name") or "").strip()
                if not reg or not name:
                    errors.append(f"Row {i}: missing reg_number or full_name")
                    continue
                if Student.query.filter_by(reg_number=reg).first():
                    skipped += 1
                    continue
                dept_id = None
                dcode = (row.get("department_code") or "").strip()
                if dcode:
                    d = Department.query.filter_by(code=dcode).first()
                    dept_id = d.id if d else None
                try:
                    yr = int(row.get("year_of_study") or 1)
                except ValueError:
                    yr = 1
                s = Student(
                    reg_number=reg, full_name=name,
                    email=(row.get("email") or "").strip() or None,
                    phone=(row.get("phone") or "").strip() or None,
                    year_of_study=yr,
                    programme=(row.get("programme") or "").strip() or None,
                    department_id=dept_id,
                )
                db.session.add(s)
                created += 1
            try:
                db.session.commit()
                log("import_csv", "student", None,
                    f"created={created} skipped={skipped} errors={len(errors)}")
            except Exception as e:
                db.session.rollback()
                flash(f"Import failed: {e}", "danger")
            summary = {"created": created, "skipped": skipped, "errors": errors}
            flash(f"Imported {created} students; {skipped} skipped.",
                  "success" if created else "warning")
    return render_template("students/import.html", form=form, summary=summary)


@students_bp.route("/template.csv")
@login_required
@role_required("officer")
def csv_template():
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["reg_number", "full_name", "email", "phone",
                "year_of_study", "programme", "department_code"])
    w.writerow(["S001", "Jane Doe", "jane@example.edu", "0700000000",
                "2", "BSc CS", "CS"])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition":
                             "attachment; filename=students_template.csv"})
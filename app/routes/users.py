from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import (StringField, PasswordField, SelectField, BooleanField,
                     SubmitField)
from wtforms.validators import DataRequired, Email, Length, Optional

from ..extensions import db
from ..models.user import User
from ..models.audit import AuditLog
from ..services.audit_service import log
from ..utils.decorators import role_required
from ..utils.pagination import paginate, apply_search

users_bp = Blueprint("users", __name__)

ROLES = [("admin", "Administrator"),
         ("officer", "Examination Officer"),
         ("invigilator", "Invigilator"),
         ("student", "Student")]


class UserForm(FlaskForm):
    username = StringField("Username",
                           validators=[DataRequired(), Length(3, 64)])
    email = StringField("Email",
                        validators=[DataRequired(), Email(), Length(3, 120)])
    full_name = StringField("Full name",
                            validators=[DataRequired(), Length(3, 120)])
    role = SelectField("Role", choices=ROLES, validators=[DataRequired()])
    is_active = BooleanField("Active", default=True)
    password = PasswordField("Password",
                             validators=[Optional(), Length(min=8, max=128)])
    submit = SubmitField("Save")


@users_bp.route("/")
@login_required
@role_required("admin")
def index():
    q = request.args.get("q", "").strip()
    role_filter = request.args.get("role", "").strip()
    query = User.query
    if role_filter:
        query = query.filter_by(role=role_filter)
    query = apply_search(query, User, q, ["username", "email", "full_name"])
    query = query.order_by(User.created_at.desc())
    page = paginate(query, per_page=20)
    return render_template("users/index.html", page=page, q=q,
                           role_filter=role_filter, roles=ROLES)


@users_bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required("admin")
def new():
    form = UserForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash("Username already exists.", "danger")
        elif User.query.filter_by(email=form.email.data).first():
            flash("Email already in use.", "danger")
        elif not form.password.data:
            flash("Password is required for a new user.", "danger")
        else:
            u = User(username=form.username.data.strip(),
                     email=form.email.data.strip(),
                     full_name=form.full_name.data.strip(),
                     role=form.role.data,
                     is_active=form.is_active.data)
            u.set_password(form.password.data)
            db.session.add(u)
            db.session.commit()
            log("create", "user", u.id,
                f"username={u.username} role={u.role}")
            flash("User created.", "success")
            return redirect(url_for("users.index"))
    return render_template("users/form.html", form=form, title="New User")


@users_bp.route("/<int:uid>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def edit(uid):
    u = User.query.get_or_404(uid)
    form = UserForm(obj=u)
    if form.validate_on_submit():
        existing = User.query.filter(User.username == form.username.data,
                                     User.id != u.id).first()
        if existing:
            flash("Username already exists.", "danger")
        else:
            email_clash = User.query.filter(User.email == form.email.data,
                                            User.id != u.id).first()
            if email_clash:
                flash("Email already in use.", "danger")
            else:
                # Guard: never let the last active admin demote themselves
                if (u.role == "admin" and form.role.data != "admin"
                        and User.query.filter_by(role="admin",
                                                 is_active=True).count() == 1):
                    flash("Cannot change role: this is the only active admin.",
                          "danger")
                else:
                    u.username = form.username.data.strip()
                    u.email = form.email.data.strip()
                    u.full_name = form.full_name.data.strip()
                    u.role = form.role.data
                    u.is_active = form.is_active.data
                    if form.password.data:
                        u.set_password(form.password.data)
                    db.session.commit()
                    log("update", "user", u.id)
                    flash("User updated.", "success")
                    return redirect(url_for("users.index"))
    return render_template("users/form.html", form=form,
                           title=f"Edit {u.username}")


@users_bp.route("/<int:uid>/toggle", methods=["POST"])
@login_required
@role_required("admin")
def toggle(uid):
    u = User.query.get_or_404(uid)
    if u.id == current_user.id:
        flash("You cannot deactivate your own account.", "danger")
        return redirect(url_for("users.index"))
    if (u.role == "admin" and u.is_active
            and User.query.filter_by(role="admin", is_active=True).count() == 1):
        flash("Cannot deactivate the only active admin.", "danger")
        return redirect(url_for("users.index"))
    u.is_active = not u.is_active
    db.session.commit()
    log("toggle_active", "user", u.id, f"active={u.is_active}")
    flash(f"User {'activated' if u.is_active else 'deactivated'}.", "success")
    return redirect(url_for("users.index"))


@users_bp.route("/<int:uid>/reset", methods=["POST"])
@login_required
@role_required("admin")
def reset_password(uid):
    u = User.query.get_or_404(uid)
    new_password = request.form.get("new_password", "")
    if len(new_password) < 8:
        flash("Password must be at least 8 characters.", "danger")
    else:
        u.set_password(new_password)
        u.failed_login_attempts = 0
        u.locked_until = None
        db.session.commit()
        log("reset_password", "user", u.id)
        flash(f"Password reset for {u.username}.", "success")
    return redirect(url_for("users.index"))


@users_bp.route("/audit")
@login_required
@role_required("admin")
def audit_log():
    q = AuditLog.query
    action = request.args.get("action", "").strip()
    user = request.args.get("user", "").strip()
    if action:
        q = q.filter(AuditLog.action == action)
    if user:
        q = q.filter(AuditLog.username.ilike(f"%{user}%"))
    q = q.order_by(AuditLog.created_at.desc())
    page = paginate(q, per_page=50)
    actions = [a[0] for a in
               db.session.query(AuditLog.action).distinct().all()]
    return render_template("users/audit_log.html", page=page,
                           action=action, user=user, actions=actions)
from datetime import datetime, timedelta
from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, current_app)
from flask_login import (login_user, logout_user, login_required,
                         current_user)
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo

from ..extensions import db
from ..models.user import User
from ..services.audit_service import log

auth_bp = Blueprint("auth", __name__)


class LoginForm(FlaskForm):
    username = StringField("Username",
                           validators=[DataRequired(), Length(3, 64)])
    password = PasswordField("Password",
                             validators=[DataRequired(), Length(6, 128)])
    remember = BooleanField("Remember me")
    submit = SubmitField("Sign in")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current password",
                                     validators=[DataRequired()])
    new_password = PasswordField("New password", validators=[
        DataRequired(), Length(min=8, max=128)
    ])
    confirm = PasswordField("Confirm new password", validators=[
        DataRequired(),
        EqualTo("new_password", message="Passwords must match."),
    ])
    submit = SubmitField("Change password")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if not user:
            flash("Invalid username or password.", "danger")
            return render_template("auth/login.html", form=form)

        if not user.is_active:
            flash("This account is deactivated. Contact an administrator.",
                  "warning")
            return render_template("auth/login.html", form=form)

        if user.locked_until and user.locked_until > datetime.utcnow():
            remaining = (user.locked_until - datetime.utcnow()).seconds // 60
            flash(f"Account locked. Try again in {remaining + 1} minutes.",
                  "danger")
            return render_template("auth/login.html", form=form)

        if not user.check_password(form.password.data):
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= current_app.config["LOGIN_MAX_ATTEMPTS"]:
                user.locked_until = datetime.utcnow() + timedelta(
                    seconds=current_app.config["LOGIN_LOCKOUT_SECONDS"]
                )
            db.session.commit()
            flash("Invalid username or password.", "danger")
            return render_template("auth/login.html", form=form)

        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.utcnow()
        db.session.commit()

        login_user(user, remember=form.remember.data)
        log("login", "user", user.id)
        flash(f"Welcome back, {user.full_name}.", "success")
        next_url = request.args.get("next")
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect(url_for("dashboard.index"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    log("logout", "user", current_user.id)
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Current password is incorrect.", "danger")
        else:
            current_user.set_password(form.new_password.data)
            db.session.commit()
            log("change_password", "user", current_user.id)
            flash("Password updated successfully.", "success")
            return redirect(url_for("dashboard.index"))
    return render_template("auth/change_password.html", form=form)
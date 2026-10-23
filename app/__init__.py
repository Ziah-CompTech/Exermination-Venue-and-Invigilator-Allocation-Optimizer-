from flask import Flask, render_template
from .config import get_config
from .extensions import db, login_manager, csrf, migrate


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(get_config(config_name))

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)

    from . import models  # noqa: F401

    from .models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    _register_blueprints(app)
    _register_error_handlers(app)
    _register_jinja_helpers(app)

    @app.context_processor
    def inject_globals():
        from flask import current_app
        from .models.notification import Notification
        from .models.allocation import InstitutionSettings
        from flask_login import current_user

        unread = 0
        if current_user.is_authenticated:
            unread = Notification.query.filter_by(
                user_id=current_user.id, is_read=False
            ).count()

        try:
            inst_name = InstitutionSettings.get().institution_name
        except Exception:
            inst_name = current_app.config.get("INSTITUTION_NAME", "Institution")

        return {
            "institution_name": inst_name,
            "unread_notifications": unread,
        }

    return app


def _register_blueprints(app: Flask) -> None:
    from .routes.auth import auth_bp
    from .routes.dashboard import dashboard_bp
    from .routes.users import users_bp
    from .routes.students import students_bp
    from .routes.subjects import subjects_bp
    from .routes.examinations import examinations_bp
    from .routes.venues import venues_bp
    from .routes.invigilators import invigilators_bp
    from .routes.allocations import allocations_bp
    from .routes.reports import reports_bp
    from .routes.notifications import notifications_bp
    from .routes.settings import settings_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(users_bp, url_prefix="/users")
    app.register_blueprint(students_bp, url_prefix="/students")
    app.register_blueprint(subjects_bp, url_prefix="/subjects")
    app.register_blueprint(examinations_bp, url_prefix="/examinations")
    app.register_blueprint(venues_bp, url_prefix="/venues")
    app.register_blueprint(invigilators_bp, url_prefix="/invigilators")
    app.register_blueprint(allocations_bp, url_prefix="/allocations")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(notifications_bp, url_prefix="/notifications")
    app.register_blueprint(settings_bp, url_prefix="/settings")


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500


def _register_jinja_helpers(app: Flask) -> None:
    @app.template_filter("dt")
    def _fmt_dt(value, fmt="%Y-%m-%d %H:%M"):
        return value.strftime(fmt) if value else ""

    @app.template_filter("d")
    def _fmt_d(value, fmt="%Y-%m-%d"):
        return value.strftime(fmt) if value else ""
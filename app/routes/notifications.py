from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from ..extensions import db
from ..models.notification import Notification

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/")
@login_required
def index():
    items = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.created_at.desc()
    ).all()
    return render_template("notifications/index.html", items=items)


@notifications_bp.route("/<int:nid>/read", methods=["POST"])
@login_required
def mark_read(nid):
    n = Notification.query.filter_by(id=nid,
                                     user_id=current_user.id).first_or_404()
    n.is_read = True
    db.session.commit()
    return jsonify({"ok": True})


@notifications_bp.route("/read-all", methods=["POST"])
@login_required
def read_all():
    Notification.query.filter_by(user_id=current_user.id,
                                 is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify({"ok": True})


@notifications_bp.route("/<int:nid>/goto")
@login_required
def goto(nid):
    from flask import redirect, url_for
    n = Notification.query.filter_by(id=nid,
                                     user_id=current_user.id).first_or_404()
    n.is_read = True
    db.session.commit()
    return redirect(n.link or url_for("notifications.index"))
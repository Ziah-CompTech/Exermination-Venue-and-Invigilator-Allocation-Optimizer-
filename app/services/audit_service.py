from flask import request
from flask_login import current_user
from ..extensions import db
from ..models.audit import AuditLog


def log(action: str, entity: str | None = None, entity_id: int | None = None,
        details: str | None = None) -> None:
    try:
        uid = current_user.id if current_user.is_authenticated else None
        uname = current_user.username if current_user.is_authenticated else None
    except Exception:
        uid, uname = None, None

    entry = AuditLog(
        user_id=uid, username=uname, action=action,
        entity=entity, entity_id=entity_id, details=details,
        ip_address=request.remote_addr if request else None,
    )
    db.session.add(entry)
    db.session.commit()
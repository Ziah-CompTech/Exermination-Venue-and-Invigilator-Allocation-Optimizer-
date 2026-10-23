from functools import wraps
from flask import abort, redirect, url_for
from flask_login import current_user


def role_required(*roles: str):
    """Restrict view to specified roles. Admin always allowed."""
    allowed = set(roles) | {"admin"}

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            if current_user.role not in allowed:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def roles(*roles: str):
    return role_required(*roles)
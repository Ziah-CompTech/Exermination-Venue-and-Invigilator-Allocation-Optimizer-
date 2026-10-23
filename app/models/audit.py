from datetime import datetime
from ..extensions import db


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    username = db.Column(db.String(64))
    action = db.Column(db.String(64), nullable=False, index=True)
    entity = db.Column(db.String(64), index=True)
    entity_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow,
                           nullable=False, index=True)

    user = db.relationship("User", foreign_keys=[user_id])
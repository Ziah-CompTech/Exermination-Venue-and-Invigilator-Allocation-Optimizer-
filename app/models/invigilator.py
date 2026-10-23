from datetime import datetime
from ..extensions import db


class Invigilator(db.Model):
    __tablename__ = "invigilators"

    id = db.Column(db.Integer, primary_key=True)
    staff_number = db.Column(db.String(32), unique=True, nullable=False,
                             index=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(32))
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_external = db.Column(db.Boolean, default=False, nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    department = db.relationship("Department", back_populates="invigilators")
    user = db.relationship("User", back_populates="invigilator",
                           foreign_keys=[user_id])
    subjects_taught = db.relationship(
        "InvigilatorSubject", back_populates="invigilator",
        cascade="all, delete-orphan"
    )
    availability = db.relationship(
        "InvigilatorAvailability", back_populates="invigilator",
        cascade="all, delete-orphan"
    )
    assignments = db.relationship(
        "InvigilatorAssignment", back_populates="invigilator",
        cascade="all, delete-orphan"
    )
    workload_limit = db.relationship(
        "InvigilatorWorkloadLimit", back_populates="invigilator",
        uselist=False, cascade="all, delete-orphan"
    )

    def teaches_subject(self, subject_id: int) -> bool:
        return any(s.subject_id == subject_id for s in self.subjects_taught)

    def __repr__(self) -> str:
        return f"<Invigilator {self.staff_number}>"


class InvigilatorSubject(db.Model):
    __tablename__ = "invigilator_subjects"
    __table_args__ = (
        db.UniqueConstraint("invigilator_id", "subject_id",
                            name="uq_invigilator_subject"),
    )

    id = db.Column(db.Integer, primary_key=True)
    invigilator_id = db.Column(db.Integer, db.ForeignKey("invigilators.id"),
                               nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"),
                           nullable=False, index=True)

    invigilator = db.relationship("Invigilator",
                                  back_populates="subjects_taught")
    subject = db.relationship("Subject", back_populates="taught_by")


class InvigilatorAvailability(db.Model):
    __tablename__ = "invigilator_availability"

    id = db.Column(db.Integer, primary_key=True)
    invigilator_id = db.Column(db.Integer, db.ForeignKey("invigilators.id"),
                               nullable=False, index=True)
    start_dt = db.Column(db.DateTime, nullable=False)
    end_dt = db.Column(db.DateTime, nullable=False)
    is_available = db.Column(db.Boolean, default=True, nullable=False)
    reason = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    invigilator = db.relationship("Invigilator", back_populates="availability")


class InvigilatorWorkloadLimit(db.Model):
    __tablename__ = "invigilator_workload_limits"

    id = db.Column(db.Integer, primary_key=True)
    invigilator_id = db.Column(db.Integer, db.ForeignKey("invigilators.id"),
                               unique=True, nullable=False)
    max_per_day = db.Column(db.Integer, default=2, nullable=False)
    max_per_period = db.Column(db.Integer, default=10, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    invigilator = db.relationship("Invigilator", back_populates="workload_limit")


class InvigilatorAssignment(db.Model):
    __tablename__ = "invigilator_assignments"
    __table_args__ = (
        db.UniqueConstraint("session_id", "invigilator_id",
                            name="uq_session_invigilator"),
        db.Index("ix_ia_inv_session", "invigilator_id", "session_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("allocation_runs.id"),
                       nullable=True, index=True)
    session_id = db.Column(db.Integer,
                           db.ForeignKey("examination_sessions.id"),
                           nullable=False, index=True)
    invigilator_id = db.Column(db.Integer, db.ForeignKey("invigilators.id"),
                               nullable=False, index=True)
    is_manual = db.Column(db.Boolean, default=False, nullable=False)
    role = db.Column(db.String(32), default="invigilator")
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    run = db.relationship("AllocationRun",
                          back_populates="invigilator_assignments")
    session = db.relationship("ExaminationSession",
                              back_populates="invigilator_assignments")
    invigilator = db.relationship("Invigilator", back_populates="assignments")
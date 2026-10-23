from datetime import datetime
from ..extensions import db


class AllocationRun(db.Model):
    __tablename__ = "allocation_runs"

    id = db.Column(db.Integer, primary_key=True)
    exam_period = db.Column(db.String(32), nullable=False, index=True)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    status = db.Column(db.String(16), default="pending", nullable=False)
    approved = db.Column(db.Boolean, default=False, nullable=False)
    published = db.Column(db.Boolean, default=False, nullable=False)
    objective_value = db.Column(db.Float)
    solver_wall_time = db.Column(db.Float)
    diagnostics = db.Column(db.Text)
    parameters = db.Column(db.Text)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    approved_at = db.Column(db.DateTime)
    published_at = db.Column(db.DateTime)

    created_by = db.relationship("User", foreign_keys=[created_by_id])
    venue_allocations = db.relationship(
        "VenueAllocation", back_populates="run",
        cascade="all, delete-orphan"
    )
    invigilator_assignments = db.relationship(
        "InvigilatorAssignment", back_populates="run",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<AllocationRun {self.id} {self.status}>"


class InstitutionSettings(db.Model):
    __tablename__ = "institution_settings"

    id = db.Column(db.Integer, primary_key=True)
    institution_name = db.Column(db.String(180), nullable=False,
                                 default="Demo University")
    default_safety_margin = db.Column(db.Integer, nullable=False, default=0)
    solver_max_time_seconds = db.Column(db.Integer, nullable=False, default=30)
    default_invigilators_per_session = db.Column(db.Integer, nullable=False,
                                                 default=1)
    default_max_duties_per_day = db.Column(db.Integer, nullable=False, default=2)
    default_max_duties_per_period = db.Column(db.Integer, nullable=False,
                                              default=10)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow, nullable=False)

    @classmethod
    def get(cls):
        s = cls.query.first()
        if not s:
            s = cls()
            db.session.add(s)
            db.session.commit()
        return s
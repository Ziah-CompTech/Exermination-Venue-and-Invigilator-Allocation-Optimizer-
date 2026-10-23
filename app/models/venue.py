from datetime import datetime
from ..extensions import db


class Venue(db.Model):
    __tablename__ = "venues"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    building = db.Column(db.String(120))
    location = db.Column(db.String(120))
    capacity = db.Column(db.Integer, nullable=False)
    usable_capacity = db.Column(db.Integer)
    venue_type = db.Column(db.String(32), default="lecture_hall", nullable=False)
    facilities = db.Column(db.Text)
    is_accessible = db.Column(db.Boolean, default=False, nullable=False)
    accessibility_notes = db.Column(db.Text)
    status = db.Column(db.String(16), default="available", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    unavailability = db.relationship(
        "VenueAvailability", back_populates="venue",
        cascade="all, delete-orphan"
    )
    allocations = db.relationship(
        "VenueAllocation", back_populates="venue",
        cascade="all, delete-orphan"
    )

    @property
    def effective_capacity(self) -> int:
        return self.usable_capacity if self.usable_capacity else self.capacity

    @property
    def facility_list(self) -> list[str]:
        if not self.facilities:
            return []
        return [f.strip().lower() for f in self.facilities.split(",")
                if f.strip()]

    def __repr__(self) -> str:
        return f"<Venue {self.code} cap={self.capacity}>"


class VenueAvailability(db.Model):
    __tablename__ = "venue_availability"

    id = db.Column(db.Integer, primary_key=True)
    venue_id = db.Column(db.Integer, db.ForeignKey("venues.id"),
                         nullable=False, index=True)
    start_dt = db.Column(db.DateTime, nullable=False)
    end_dt = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    venue = db.relationship("Venue", back_populates="unavailability")


class VenueAllocation(db.Model):
    __tablename__ = "venue_allocations"
    __table_args__ = (
        db.Index("ix_va_session_venue", "session_id", "venue_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("allocation_runs.id"),
                       nullable=True, index=True)
    session_id = db.Column(db.Integer,
                           db.ForeignKey("examination_sessions.id"),
                           nullable=False, index=True)
    venue_id = db.Column(db.Integer, db.ForeignKey("venues.id"),
                         nullable=False, index=True)
    candidates_assigned = db.Column(db.Integer, nullable=False, default=0)
    is_manual = db.Column(db.Boolean, default=False, nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    run = db.relationship("AllocationRun", back_populates="venue_allocations")
    session = db.relationship("ExaminationSession",
                              back_populates="venue_allocations")
    venue = db.relationship("Venue", back_populates="allocations")
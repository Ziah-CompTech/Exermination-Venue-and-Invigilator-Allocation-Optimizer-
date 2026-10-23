from datetime import datetime
from ..extensions import db


class Examination(db.Model):
    __tablename__ = "examinations"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"),
                           nullable=False, index=True)
    exam_period = db.Column(db.String(32), default="2025-S1", nullable=False)
    registered_candidates = db.Column(db.Integer, nullable=False, default=0)
    is_estimated = db.Column(db.Boolean, default=False, nullable=False)
    required_venue_type = db.Column(db.String(32), default="any", nullable=False)
    required_facilities = db.Column(db.String(200))
    special_requirements = db.Column(db.Text)
    invigilators_required = db.Column(db.Integer, default=1, nullable=False)
    status = db.Column(db.String(16), default="draft", nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow, nullable=False)

    subject = db.relationship("Subject", back_populates="examinations")
    sessions = db.relationship(
        "ExaminationSession", back_populates="examination",
        cascade="all, delete-orphan"
    )

    @property
    def required_facility_list(self) -> list[str]:
        if not self.required_facilities:
            return []
        return [f.strip().lower() for f in self.required_facilities.split(",")
                if f.strip()]

    def __repr__(self) -> str:
        return f"<Examination {self.title}>"


class ExaminationSession(db.Model):
    __tablename__ = "examination_sessions"
    __table_args__ = (
        db.Index("ix_session_dt", "exam_date", "start_time"),
    )

    id = db.Column(db.Integer, primary_key=True)
    examination_id = db.Column(db.Integer,
                              db.ForeignKey("examinations.id"),
                              nullable=False, index=True)
    exam_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    expected_candidates = db.Column(db.Integer, nullable=False)
    required_invigilators = db.Column(db.Integer, default=1, nullable=False)
    status = db.Column(db.String(16), default="unallocated", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    examination = db.relationship("Examination", back_populates="sessions")
    venue_allocations = db.relationship(
        "VenueAllocation", back_populates="session",
        cascade="all, delete-orphan"
    )
    invigilator_assignments = db.relationship(
        "InvigilatorAssignment", back_populates="session",
        cascade="all, delete-orphan"
    )
    candidate_allocations = db.relationship(
        "CandidateAllocation", back_populates="session",
        cascade="all, delete-orphan"
    )

    @property
    def start_dt(self):
        return datetime.combine(self.exam_date, self.start_time)

    @property
    def end_dt(self):
        return datetime.combine(self.exam_date, self.end_time)

    @property
    def allocated_capacity(self) -> int:
        if not self.venue_allocations:
            return 0
        return sum(va.venue.effective_capacity for va in self.venue_allocations)

    def __repr__(self) -> str:
        return (f"<Session {self.id} {self.exam_date} "
                f"{self.start_time}-{self.end_time}>")


class CandidateAllocation(db.Model):
    __tablename__ = "candidate_allocations"
    __table_args__ = (
        db.UniqueConstraint("session_id", "student_id",
                            name="uq_session_student"),
    )

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer,
                           db.ForeignKey("examination_sessions.id"),
                           nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"),
                           nullable=False, index=True)
    venue_id = db.Column(db.Integer, db.ForeignKey("venues.id"),
                         nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    session = db.relationship("ExaminationSession",
                              back_populates="candidate_allocations")
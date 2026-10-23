from datetime import datetime
from ..extensions import db


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    reg_number = db.Column(db.String(32), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), index=True)
    phone = db.Column(db.String(32))
    year_of_study = db.Column(db.Integer, default=1, nullable=False)
    programme = db.Column(db.String(120))
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    department = db.relationship("Department", back_populates="students")
    user = db.relationship("User", back_populates="student",
                           foreign_keys=[user_id])
    registrations = db.relationship(
        "StudentSubjectRegistration", back_populates="student",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Student {self.reg_number}>"


class StudentSubjectRegistration(db.Model):
    __tablename__ = "student_subject_registrations"
    __table_args__ = (
        db.UniqueConstraint("student_id", "subject_id", name="uq_student_subject"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"),
                           nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"),
                           nullable=False, index=True)
    exam_period = db.Column(db.String(32), default="2025-S1", nullable=False)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    student = db.relationship("Student", back_populates="registrations")
    subject = db.relationship("Subject", back_populates="student_registrations")
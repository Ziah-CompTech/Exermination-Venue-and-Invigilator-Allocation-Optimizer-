from datetime import datetime
from ..extensions import db


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    students = db.relationship("Student", back_populates="department")
    invigilators = db.relationship("Invigilator", back_populates="department")
    subjects = db.relationship("Subject", back_populates="department")


class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    credit_hours = db.Column(db.Integer, default=3, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    department = db.relationship("Department", back_populates="subjects")
    examinations = db.relationship("Examination", back_populates="subject",
                                   cascade="all, delete-orphan")
    student_registrations = db.relationship(
        "StudentSubjectRegistration", back_populates="subject",
        cascade="all, delete-orphan"
    )
    taught_by = db.relationship(
        "InvigilatorSubject", back_populates="subject",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Subject {self.code}>"
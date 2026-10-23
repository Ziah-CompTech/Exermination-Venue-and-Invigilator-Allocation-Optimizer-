"""
Populate the database with a realistic demonstration dataset.

Usage:
    python scripts/seed_demo_data.py            # add missing data only
    python scripts/seed_demo_data.py --reset    # drop and recreate all tables

WARNING: --reset destroys all existing data.
"""
import argparse
import os
import sys
from datetime import date, time, timedelta, datetime

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.student import Student, StudentSubjectRegistration
from app.models.subject import Department, Subject
from app.models.examination import Examination, ExaminationSession
from app.models.venue import Venue, VenueAvailability
from app.models.invigilator import (Invigilator, InvigilatorSubject,
                                    InvigilatorAvailability,
                                    InvigilatorWorkloadLimit)
from app.models.allocation import InstitutionSettings


DEMO_PASSWORD = "Password123!"


def _mk_user(username, email, full_name, role):
    u = User.query.filter_by(username=username).first()
    if u:
        return u
    u = User(username=username, email=email, full_name=full_name,
             role=role, is_active=True)
    u.set_password(DEMO_PASSWORD)
    db.session.add(u)
    db.session.flush()
    return u


def _dept(code, name):
    d = Department.query.filter_by(code=code).first()
    if d:
        return d
    d = Department(code=code, name=name)
    db.session.add(d)
    db.session.flush()
    return d


def _subj(code, title, dept, credits=3):
    s = Subject.query.filter_by(code=code).first()
    if s:
        return s
    s = Subject(code=code, title=title, department_id=dept.id,
                credit_hours=credits)
    db.session.add(s)
    db.session.flush()
    return s


def _venue(code, name, building, capacity, vtype, facilities,
           accessible=False, status="available"):
    v = Venue.query.filter_by(code=code).first()
    if v:
        return v
    v = Venue(code=code, name=name, building=building, location=building,
              capacity=capacity, venue_type=vtype, facilities=facilities,
              is_accessible=accessible, status=status)
    db.session.add(v)
    db.session.flush()
    return v


def _inv(staff_no, name, dept, teaches=None, user=None,
         external=False, max_per_day=2, max_per_period=10):
    i = Invigilator.query.filter_by(staff_number=staff_no).first()
    if i:
        return i
    i = Invigilator(staff_number=staff_no, full_name=name,
                    email=f"{staff_no.lower()}@demo.edu",
                    department_id=dept.id if dept else None,
                    is_external=external,
                    user_id=user.id if user else None)
    db.session.add(i)
    db.session.flush()
    for subj in (teaches or []):
        db.session.add(InvigilatorSubject(invigilator_id=i.id,
                                          subject_id=subj.id))
    db.session.add(InvigilatorWorkloadLimit(
        invigilator_id=i.id, max_per_day=max_per_day,
        max_per_period=max_per_period))
    return i


def _stu(reg, name, dept, yr=2, prog="BSc", user=None):
    st = Student.query.filter_by(reg_number=reg).first()
    if st:
        return st
    st = Student(reg_number=reg, full_name=name,
                 email=f"{reg.lower()}@student.demo.edu",
                 year_of_study=yr, programme=prog,
                 department_id=dept.id, user_id=user.id if user else None)
    db.session.add(st)
    db.session.flush()
    return st


def _reg(stu, subj):
    exists = StudentSubjectRegistration.query.filter_by(
        student_id=stu.id, subject_id=subj.id).first()
    if exists:
        return
    db.session.add(StudentSubjectRegistration(
        student_id=stu.id, subject_id=subj.id, exam_period="2025-S1"))


def _exam(title, subj, candidates, inv_needed=1,
          vtype="any", facilities=None, estimated=False):
    e = Examination.query.filter_by(title=title,
                                    subject_id=subj.id).first()
    if e:
        return e
    e = Examination(
        title=title, subject_id=subj.id, exam_period="2025-S1",
        registered_candidates=candidates,
        is_estimated=estimated,
        required_venue_type=vtype,
        required_facilities=facilities,
        invigilators_required=inv_needed,
        status="scheduled",
    )
    db.session.add(e)
    db.session.flush()
    return e


def _session(exam, day_offset, start_h, start_m, end_h, end_m,
             candidates=None, inv=None):
    base = _next_monday()
    d = base + timedelta(days=day_offset)
    existing = ExaminationSession.query.filter_by(
        examination_id=exam.id, exam_date=d,
        start_time=time(start_h, start_m)).first()
    if existing:
        return existing
    s = ExaminationSession(
        examination_id=exam.id, exam_date=d,
        start_time=time(start_h, start_m),
        end_time=time(end_h, end_m),
        expected_candidates=candidates or exam.registered_candidates,
        required_invigilators=inv or exam.invigilators_required,
    )
    db.session.add(s)
    db.session.flush()
    return s


def _next_monday():
    today = date.today()
    days = (7 - today.weekday()) % 7 or 7
    return today + timedelta(days=days)


def seed(reset=False):
    app = create_app()
    with app.app_context():
        if reset:
            db.drop_all()
        db.create_all()

        # ---------- Institution settings ---------- #
        s = InstitutionSettings.get()
        s.institution_name = "Demo University"
        s.default_safety_margin = 0
        s.solver_max_time_seconds = 30
        db.session.commit()

        # ---------- Users ---------- #
        _mk_user("admin", "admin@demo.edu", "System Administrator", "admin")
        _mk_user("officer", "officer@demo.edu", "Grace Exams", "officer")
        inv_user_1 = _mk_user("inv_dr_kamau", "kamau@demo.edu",
                              "Dr. Alice Kamau", "invigilator")
        inv_user_2 = _mk_user("inv_mr_okoro", "okoro@demo.edu",
                              "Mr. Ben Okoro", "invigilator")
        stu_user_1 = _mk_user("stu_001", "s001@student.demo.edu",
                              "Jane First", "student")

        # ---------- Departments ---------- #
        cs = _dept("CS", "Computer Science")
        math = _dept("MATH", "Mathematics")
        bus = _dept("BUS", "Business")

        # ---------- Subjects ---------- #
        sub_cs101 = _subj("CS101", "Introduction to Programming", cs)
        sub_cs201 = _subj("CS201", "Data Structures & Algorithms", cs)
        sub_ma101 = _subj("MA101", "Calculus I", math)
        sub_ma202 = _subj("MA202", "Linear Algebra", math)
        sub_bu101 = _subj("BU101", "Principles of Management", bus)

        # ---------- Venues ---------- #
        v_hall_a = _venue("HA", "Hall A", "Main Block", 200, "exam_hall",
                          "projector,ac,accessible", accessible=True)
        v_hall_b = _venue("HB", "Hall B", "Main Block", 120, "exam_hall",
                          "projector,ac")
        v_lab_1 = _venue("LAB1", "Computer Lab 1", "Science Block", 40, "lab",
                         "computers,projector,ac")
        v_lab_2 = _venue("LAB2", "Computer Lab 2", "Science Block", 30, "lab",
                         "computers,projector")
        v_sem = _venue("SR1", "Seminar Room 1", "Annex", 25, "seminar_room",
                       "projector")
        v_maint = _venue("MAINT1", "Old Hall", "West Wing", 100,
                         "exam_hall", "projector", status="maintenance")

        # A maintenance block on Hall B for testing
        if not v_hall_b.unavailability:
            db.session.add(VenueAvailability(
                venue_id=v_hall_b.id,
                start_dt=datetime.combine(_next_monday() + timedelta(days=2),
                                          time(8, 0)),
                end_dt=datetime.combine(_next_monday() + timedelta(days=2),
                                        time(18, 0)),
                reason="Fire safety inspection",
            ))

        # ---------- Invigilators ---------- #
        i_kamau = _inv("STF1001", "Dr. Alice Kamau", cs,
                       teaches=[sub_cs101, sub_cs201], user=inv_user_1)
        i_okoro = _inv("STF1002", "Mr. Ben Okoro", math,
                       teaches=[sub_ma101, sub_ma202], user=inv_user_2)
        i_adeyemi = _inv("STF1003", "Ms. Chiara Adeyemi", bus,
                         teaches=[sub_bu101])
        i_brown = _inv("STF1004", "Mr. Chris Brown", cs, teaches=[],
                       external=True, max_per_day=3, max_per_period=15)
        i_davis = _inv("STF1005", "Mrs. Diana Davis", bus, teaches=[],
                       max_per_day=2, max_per_period=12)

        # Give one invigilator an explicit unavailable window
        if not i_adeyemi.availability:
            db.session.add(InvigilatorAvailability(
                invigilator_id=i_adeyemi.id,
                start_dt=datetime.combine(
                    _next_monday() + timedelta(days=1), time(0, 0)),
                end_dt=datetime.combine(
                    _next_monday() + timedelta(days=1), time(23, 59)),
                is_available=False,
                reason="Annual leave",
            ))

        # ---------- Students ---------- #
        students_cs = []
        for i in range(5):
            reg = f"S00{i+1}"
            stu = _stu(reg, f"CS Student {i+1}", cs,
                       prog="BSc CS",
                       user=stu_user_1 if i == 0 else None)
            students_cs.append(stu)
            _reg(stu, sub_cs101)
            _reg(stu, sub_cs201)

        students_math = []
        for i in range(3):
            reg = f"S10{i+1}"
            stu = _stu(reg, f"Math Student {i+1}", math, prog="BSc Math")
            students_math.append(stu)
            _reg(stu, sub_ma101)
            _reg(stu, sub_ma202)

        students_bus = []
        for i in range(2):
            reg = f"S20{i+1}"
            stu = _stu(reg, f"Business Student {i+1}", bus, prog="BBA")
            students_bus.append(stu)
            _reg(stu, sub_bu101)

        # ---------- Examinations ---------- #
        exam1 = _exam("CS101 End of Semester Exam", sub_cs101, candidates=5,
                      inv_needed=1, vtype="exam_hall", facilities="projector")
        exam2 = _exam("CS201 End of Semester Exam", sub_cs201, candidates=5,
                      inv_needed=1, vtype="exam_hall", facilities="projector")
        exam3 = _exam("MA101 End of Semester Exam", sub_ma101, candidates=3,
                      inv_needed=1, vtype="any")
        exam4 = _exam("MA202 End of Semester Exam", sub_ma202, candidates=3,
                      inv_needed=1, vtype="any")
        exam5 = _exam("BU101 End of Semester Exam", sub_bu101, candidates=2,
                      inv_needed=1, vtype="any")
        exam6 = _exam("CS101 Combined Large Sitting", sub_cs101,
                      candidates=180, inv_needed=3, vtype="exam_hall",
                      facilities="projector")

        # ---------- Sessions ---------- #
        _session(exam1, 0, 9, 0, 11, 0)
        _session(exam2, 1, 9, 0, 11, 0)
        _session(exam3, 1, 14, 0, 16, 0)
        _session(exam4, 2, 9, 0, 11, 0)
        _session(exam5, 2, 14, 0, 16, 0)
        _session(exam6, 3, 9, 0, 12, 0)

        db.session.commit()

        # ---------- Summary ---------- #
        print("=" * 62)
        print("Demo data seeded successfully.")
        print("=" * 62)
        print(f"Users:        {User.query.count()}")
        print(f"Departments:  {Department.query.count()}")
        print(f"Subjects:     {Subject.query.count()}")
        print(f"Venues:       {Venue.query.count()}")
        print(f"Invigilators: {Invigilator.query.count()}")
        print(f"Students:     {Student.query.count()}")
        print(f"Examinations: {Examination.query.count()}")
        print(f"Sessions:     {ExaminationSession.query.count()}")
        print()
        print("Demo login credentials (LOCAL DEVELOPMENT ONLY):")
        print("  admin         / Password123!  (Administrator)")
        print("  officer       / Password123!  (Examination Officer)")
        print("  inv_dr_kamau  / Password123!  (Invigilator)")
        print("  stu_001       / Password123!  (Student)")
        print()
        print("IMPORTANT: change these before any deployment.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true",
                        help="Drop and recreate all tables first")
    args = parser.parse_args()
    seed(reset=args.reset)
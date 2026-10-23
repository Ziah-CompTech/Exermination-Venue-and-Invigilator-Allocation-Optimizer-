"""
Pytest fixtures.

Tests run against a test database. By default TEST_DATABASE_URL from .env
is used (MySQL); if unset, an in-memory SQLite database is used as a
portable fallback so the suite can run anywhere.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("FLASK_ENV", "testing")

from app import create_app
from app.extensions import db as _db
from app.models.user import User
from app.models.student import Student, StudentSubjectRegistration
from app.models.subject import Department, Subject
from app.models.examination import Examination, ExaminationSession
from app.models.venue import Venue
from app.models.invigilator import (Invigilator, InvigilatorSubject,
                                    InvigilatorWorkloadLimit)


@pytest.fixture(scope="session")
def app():
    app = create_app("testing")
    uri = os.environ.get("TEST_DATABASE_URL")
    if uri:
        app.config["SQLALCHEMY_DATABASE_URI"] = uri
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def session(app):
    with app.app_context():
        yield _db.session
        _db.session.rollback()


@pytest.fixture()
def admin(app):
    with app.app_context():
        u = User.query.filter_by(username="admin_test").first()
        if not u:
            u = User(username="admin_test", email="admin_test@test.local",
                     full_name="Admin Test", role="admin", is_active=True)
            u.set_password("Passw0rd!")
            _db.session.add(u)
            _db.session.commit()
        return u


@pytest.fixture()
def officer(app):
    with app.app_context():
        u = User.query.filter_by(username="officer_test").first()
        if not u:
            u = User(username="officer_test",
                     email="officer_test@test.local",
                     full_name="Officer Test", role="officer",
                     is_active=True)
            u.set_password("Passw0rd!")
            _db.session.add(u)
            _db.session.commit()
        return u


@pytest.fixture()
def login(client):
    def _login(username, password="Passw0rd!"):
        return client.post("/login",
                           data={"username": username, "password": password},
                           follow_redirects=True)
    return _login


@pytest.fixture()
def sample_subjects(app):
    with app.app_context():
        d = Department.query.filter_by(code="TST").first() or \
            Department(code="TST", name="Test Dept")
        _db.session.add(d)
        _db.session.flush()
        s1 = Subject.query.filter_by(code="TS101").first() or \
            Subject(code="TS101", title="Test Subject 1",
                    department_id=d.id)
        s2 = Subject.query.filter_by(code="TS102").first() or \
            Subject(code="TS102", title="Test Subject 2",
                    department_id=d.id)
        _db.session.add_all([s1, s2])
        _db.session.commit()
        return s1.id, s2.id, d.id


@pytest.fixture()
def sample_venues(app):
    with app.app_context():
        ids = []
        for code, cap, vtype in [("VSMALL", 10, "exam_hall"),
                                 ("VMED", 100, "exam_hall"),
                                 ("VBIG", 500, "exam_hall")]:
            v = Venue.query.filter_by(code=code).first()
            if not v:
                v = Venue(code=code, name=code, capacity=cap,
                          venue_type=vtype, status="available")
                _db.session.add(v)
                _db.session.flush()
            ids.append(v.id)
        _db.session.commit()
        return ids


@pytest.fixture()
def sample_invigilators(app, sample_subjects):
    with app.app_context():
        s1, s2, d = sample_subjects
        created = []
        for staff, teaches in [("TST001", [s1]), ("TST002", [s2]),
                               ("TST003", [])]:
            i = Invigilator.query.filter_by(staff_number=staff).first()
            if not i:
                i = Invigilator(staff_number=staff, full_name=staff,
                                department_id=d, is_active=True)
                _db.session.add(i)
                _db.session.flush()
                for sid in teaches:
                    _db.session.add(InvigilatorSubject(
                        invigilator_id=i.id, subject_id=sid))
                _db.session.add(InvigilatorWorkloadLimit(
                    invigilator_id=i.id, max_per_day=5,
                    max_per_period=20))
            created.append(i.id)
        _db.session.commit()
        return created
from datetime import date, time, timedelta

from app.extensions import db
from app.models.examination import Examination, ExaminationSession
from app.models.venue import Venue
from app.models.invigilator import Invigilator
from app.services.allocation_solver import run_full_allocation


def _mk_minimal_world():
    from app.models.subject import Subject, Department
    d = Department.query.filter_by(code="W").first() or \
        Department(code="W", name="World")
    db.session.add(d)
    db.session.flush()
    s = Subject.query.filter_by(code="W101").first() or \
        Subject(code="W101", title="W", department_id=d.id)
    db.session.add(s)
    db.session.flush()
    v = Venue.query.filter_by(code="WV").first() or \
        Venue(code="WV", name="WV", capacity=100,
              venue_type="any", status="available")
    db.session.add(v)
    db.session.flush()
    i = Invigilator.query.filter_by(staff_number="WI").first() or \
        Invigilator(staff_number="WI", full_name="WI", is_active=True)
    db.session.add(i)
    db.session.flush()
    e = Examination(title="WE", subject_id=s.id, exam_period="TESTPER",
                    registered_candidates=20, invigilators_required=1)
    db.session.add(e)
    db.session.flush()
    sess = ExaminationSession(
        examination_id=e.id,
        exam_date=date.today() + timedelta(days=1),
        start_time=time(9, 0), end_time=time(11, 0),
        expected_candidates=20, required_invigilators=1)
    db.session.add(sess)
    db.session.commit()
    return s.id, v.id, i.id, sess.id


def test_full_allocation_feasible(app, sample_venues):
    with app.app_context():
        _mk_minimal_world()
        outcome = run_full_allocation("TESTPER", max_time_seconds=5)
        assert outcome.status in ("optimal", "feasible")
        assert outcome.venue_result.assignments
        assert outcome.invigilator_result.assignments


def test_full_allocation_infeasible_no_venues(app):
    with app.app_context():
        _mk_minimal_world()
        Venue.query.delete()
        db.session.commit()
        outcome = run_full_allocation("TESTPER", max_time_seconds=5)
        assert outcome.status == "infeasible"
        assert any("venue" in d.lower() for d in outcome.diagnostics)


def test_publication_guard_requires_approval(app, client, officer, login):
    with app.app_context():
        _mk_minimal_world()
    login("officer_test")
    from app.models.allocation import AllocationRun
    with app.app_context():
        run = AllocationRun(exam_period="TESTPER", status="feasible")
        db.session.add(run)
        db.session.commit()
        rid = run.id
    r = client.post(f"/allocations/{rid}/publish", follow_redirects=True)
    assert b"Approve the run before publishing" in r.data
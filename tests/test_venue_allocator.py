from datetime import date, time, timedelta

from app.extensions import db
from app.models.examination import Examination, ExaminationSession
from app.models.venue import Venue
from app.services.venue_allocator import solve_venue_allocation


def _mk_session(subject_id, candidates, day_offset=0, start=(9, 0),
                end=(11, 0), period="2025-S1", vtype="any",
                facilities=None):
    e = Examination(title=f"E-{subject_id}-{day_offset}",
                    subject_id=subject_id, exam_period=period,
                    registered_candidates=candidates,
                    required_venue_type=vtype,
                    required_facilities=facilities,
                    invigilators_required=1)
    db.session.add(e)
    db.session.flush()
    s = ExaminationSession(
        examination_id=e.id,
        exam_date=date.today() + timedelta(days=day_offset),
        start_time=time(*start), end_time=time(*end),
        expected_candidates=candidates, required_invigilators=1)
    db.session.add(s)
    db.session.flush()
    return s


def test_capacity_never_exceeded(app, sample_subjects, sample_venues):
    with app.app_context():
        s1, _, _ = sample_subjects
        s = _mk_session(s1, candidates=80, day_offset=0)
        db.session.commit()
        venues = Venue.query.all()
        res = solve_venue_allocation([s], venues, max_time_seconds=5)
        assert res.status in ("optimal", "feasible")
        for vid, n in res.assignments[s.id].items():
            v = Venue.query.get(vid)
            assert n <= v.effective_capacity


def test_infeasible_when_total_capacity_insufficient(
        app, sample_subjects, sample_venues):
    with app.app_context():
        s1, _, _ = sample_subjects
        s = _mk_session(s1, candidates=9999, day_offset=0)
        db.session.commit()
        res = solve_venue_allocation([s], Venue.query.all(),
                                     max_time_seconds=5)
        assert res.status == "infeasible"
        assert any("capacity" in d.lower() for d in res.diagnostics)


def test_no_double_booking_across_overlapping_sessions(
        app, sample_subjects, sample_venues):
    with app.app_context():
        s1, s2, _ = sample_subjects
        a = _mk_session(s1, candidates=50, day_offset=0,
                        start=(9, 0), end=(11, 0))
        b = _mk_session(s2, candidates=50, day_offset=0,
                        start=(10, 0), end=(12, 0))
        db.session.commit()
        res = solve_venue_allocation([a, b], Venue.query.all(),
                                     max_time_seconds=5)
        assert res.status in ("optimal", "feasible")
        used_a = set(res.assignments[a.id].keys())
        used_b = set(res.assignments[b.id].keys())
        assert used_a.isdisjoint(used_b)


def test_facilities_requirement(app, sample_subjects, sample_venues):
    with app.app_context():
        s1, _, _ = sample_subjects
        s = _mk_session(s1, candidates=5,
                        facilities="electron-microscope")
        db.session.commit()
        res = solve_venue_allocation([s], Venue.query.all(),
                                     max_time_seconds=5)
        assert res.status == "infeasible"
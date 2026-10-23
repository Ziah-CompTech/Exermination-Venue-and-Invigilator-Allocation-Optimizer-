from datetime import date, time, timedelta

from app.extensions import db
from app.models.examination import Examination, ExaminationSession
from app.models.venue import Venue, VenueAllocation
from app.models.invigilator import Invigilator
from app.services import conflict_detector as cd


def _session(app, subject_id, day_offset=0, start=(9, 0), end=(11, 0),
             candidates=5, inv=1):
    with app.app_context():
        e = Examination(title=f"E{subject_id}-{day_offset}",
                        subject_id=subject_id, exam_period="2025-S1",
                        registered_candidates=candidates,
                        invigilators_required=inv)
        db.session.add(e)
        db.session.flush()
        s = ExaminationSession(
            examination_id=e.id,
            exam_date=date.today() + timedelta(days=day_offset),
            start_time=time(*start), end_time=time(*end),
            expected_candidates=candidates, required_invigilators=inv)
        db.session.add(s)
        db.session.commit()
        return s.id


def test_overlaps_half_open():
    from datetime import datetime
    a = (datetime(2025, 1, 1, 9), datetime(2025, 1, 1, 11))
    b = (datetime(2025, 1, 1, 10), datetime(2025, 1, 1, 12))
    c = (datetime(2025, 1, 1, 11), datetime(2025, 1, 1, 13))
    assert cd.overlaps(*a, *b) is True
    assert cd.overlaps(*a, *c) is False


def test_venue_capacity(app, sample_subjects, sample_venues):
    with app.app_context():
        s1, _, _ = sample_subjects
        sid = _session(app, s1, candidates=20)
        s = ExaminationSession.query.get(sid)
        small = Venue.query.filter_by(code="VSMALL").first()
        big = Venue.query.filter_by(code="VBIG").first()
        assert cd.venue_has_capacity(small, s.expected_candidates) is False
        assert cd.venue_has_capacity(big, s.expected_candidates) is True


def test_venue_double_booking(app, sample_subjects, sample_venues):
    with app.app_context():
        s1, _, _ = sample_subjects
        a_id = _session(app, s1, day_offset=0)
        b_id = _session(app, s1, day_offset=0, start=(10, 0), end=(12, 0))
        big = Venue.query.filter_by(code="VBIG").first()
        db.session.add(VenueAllocation(session_id=a_id, venue_id=big.id,
                                       candidates_assigned=10))
        db.session.commit()
        b = ExaminationSession.query.get(b_id)
        assert cd.venue_double_booked(b, big.id) is True


def test_invigilator_double_booking(app, sample_subjects, sample_invigilators):
    with app.app_context():
        s1, _, _ = sample_subjects
        a_id = _session(app, s1, day_offset=0)
        b_id = _session(app, s1, day_offset=0, start=(10, 0), end=(12, 0))
        inv_id = sample_invigilators[0]
        from app.models.invigilator import InvigilatorAssignment
        db.session.add(InvigilatorAssignment(session_id=a_id,
                                             invigilator_id=inv_id))
        db.session.commit()
        b = ExaminationSession.query.get(b_id)
        assert cd.invigilator_double_booked(inv_id, b) is True


def test_conflict_of_interest(app, sample_subjects, sample_invigilators):
    with app.app_context():
        s1, _, _ = sample_subjects
        sid = _session(app, s1)
        s = ExaminationSession.query.get(sid)
        teacher = Invigilator.query.get(sample_invigilators[0])
        neutral = Invigilator.query.get(sample_invigilators[2])
        assert cd.invigilator_teaches_subject(teacher, s1) is True
        ok, reason = cd.invigilator_eligible_for_session(teacher, s)
        assert ok is False and "teaches" in reason
        ok2, _ = cd.invigilator_eligible_for_session(neutral, s)
        assert ok2 is True


def test_student_overlap_detection(app, sample_subjects):
    with app.app_context():
        s1, s2, _ = sample_subjects
        a = _session(app, s1, day_offset=0)
        b = _session(app, s2, day_offset=0, start=(10, 0), end=(12, 0))
        from app.models.student import Student, StudentSubjectRegistration
        stu = Student(reg_number="OV1", full_name="Overlap Student")
        db.session.add(stu)
        db.session.commit()
        db.session.add_all([
            StudentSubjectRegistration(student_id=stu.id,
                                       subject_id=s1),
            StudentSubjectRegistration(student_id=stu.id,
                                       subject_id=s2),
        ])
        db.session.commit()
        a_s = ExaminationSession.query.get(a)
        b_s = ExaminationSession.query.get(b)
        shared = cd.sessions_share_students(a_s, b_s)
        assert stu.id in shared
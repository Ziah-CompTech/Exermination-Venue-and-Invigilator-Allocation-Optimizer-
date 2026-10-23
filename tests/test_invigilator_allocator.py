from datetime import date, time, timedelta

from app.extensions import db
from app.models.examination import Examination, ExaminationSession
from app.models.invigilator import (Invigilator, InvigilatorWorkloadLimit)
from app.services.invigilator_allocator import (
    solve_invigilator_allocation,
)


def _mk_session(subject_id, candidates, required, day_offset=0,
                start=(9, 0), end=(11, 0)):
    e = Examination(title=f"E-{subject_id}-{day_offset}",
                    subject_id=subject_id, exam_period="2025-S1",
                    registered_candidates=candidates,
                    invigilators_required=required)
    db.session.add(e)
    db.session.flush()
    s = ExaminationSession(
        examination_id=e.id,
        exam_date=date.today() + timedelta(days=day_offset),
        start_time=time(*start), end_time=time(*end),
        expected_candidates=candidates, required_invigilators=required)
    db.session.add(s)
    db.session.flush()
    return s


def test_never_assigns_subject_teacher(app, sample_subjects,
                                        sample_invigilators):
    with app.app_context():
        s1, _, _ = sample_subjects
        s = _mk_session(s1, candidates=5, required=1)
        db.session.commit()
        invs = Invigilator.query.filter_by(is_active=True).all()
        res = solve_invigilator_allocation([s], invs, max_time_seconds=5)
        assert res.status in ("optimal", "feasible")
        teacher = Invigilator.query.get(sample_invigilators[0])
        assert teacher.id not in res.assignments[s.id]


def test_no_overlapping_assignments(app, sample_subjects,
                                     sample_invigilators):
    with app.app_context():
        s1, s2, _ = sample_subjects
        a = _mk_session(s1, 5, 1, day_offset=0,
                        start=(9, 0), end=(11, 0))
        b = _mk_session(s2, 5, 1, day_offset=0,
                        start=(10, 0), end=(12, 0))
        db.session.commit()
        invs = Invigilator.query.filter_by(is_active=True).all()
        res = solve_invigilator_allocation([a, b], invs,
                                           max_time_seconds=5)
        assert res.status in ("optimal", "feasible")
        assert set(res.assignments[a.id]).isdisjoint(
            set(res.assignments[b.id]))


def test_infeasible_when_too_few_eligible(app, sample_subjects):
    with app.app_context():
        s1, _, _ = sample_subjects
        inv = Invigilator(staff_number="SOLO", full_name="Solo",
                          is_active=True)
        db.session.add(inv)
        db.session.flush()
        s = _mk_session(s1, 5, 3)
        db.session.commit()
        res = solve_invigilator_allocation([s], [inv],
                                           max_time_seconds=5)
        assert res.status == "infeasible"


def test_workload_limit_enforced(app, sample_subjects,
                                  sample_invigilators):
    with app.app_context():
        s1, _, _ = sample_subjects
        for i in Invigilator.query.all():
            lim = i.workload_limit or InvigilatorWorkloadLimit(
                invigilator_id=i.id, max_per_day=1, max_per_period=20)
            lim.max_per_day = 1
            db.session.add(lim)
        s_list = [_mk_session(s1, 5, 1, day_offset=0,
                              start=(9 + 3 * i, 0), end=(11 + 3 * i, 0))
                  for i in range(3)]
        db.session.commit()
        invs = Invigilator.query.filter_by(is_active=True).all()
        res = solve_invigilator_allocation(s_list, invs,
                                           max_time_seconds=5)
        used = []
        for s in s_list:
            used.extend(res.assignments.get(s.id, []))
        assert len(used) == len(set(used))
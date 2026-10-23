"""
Venue allocation via Google OR-Tools CP-SAT.

Decision variables:
    x[s, v] = number of candidates from session s assigned to venue v
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ortools.sat.python import cp_model

from ..models.venue import Venue
from ..models.examination import ExaminationSession
from .conflict_detector import session_interval, overlaps, \
    venue_eligible_for_session


@dataclass
class VenueAllocationResult:
    status: str
    wall_time: float
    objective: Optional[float] = None
    assignments: dict = field(default_factory=dict)
    diagnostics: list = field(default_factory=list)
    session_warnings: dict = field(default_factory=dict)


def _eligible_venues_for_session(session: ExaminationSession,
                                 venues):
    out = []
    for v in venues:
        ok, _ = venue_eligible_for_session(session, v)
        if ok:
            out.append(v)
    return out


def solve_venue_allocation(sessions,
                           venues,
                           max_time_seconds: int = 30,
                           allow_under_capacity: bool = False):
    started = datetime.utcnow()
    model = cp_model.CpModel()
    diagnostics = []
    session_warnings = {}

    eligibility = {}
    for s in sessions:
        elig = _eligible_venues_for_session(s, venues)
        eligibility[s.id] = elig
        if not elig:
            diagnostics.append(
                f"Session {s.id} ({s.examination.title}): no eligible venues "
                f"(type={s.examination.required_venue_type}, "
                f"facilities={s.examination.required_facility_list})."
            )
        total_cap = sum(v.effective_capacity for v in elig)
        if total_cap < s.expected_candidates:
            diagnostics.append(
                f"Session {s.id} ({s.examination.title}): eligible venue "
                f"capacity {total_cap} < candidates {s.expected_candidates}."
            )
            session_warnings[s.id] = "total eligible capacity below demand"

    if any(not eligibility[s.id] for s in sessions):
        return VenueAllocationResult(
            status="infeasible",
            wall_time=(datetime.utcnow() - started).total_seconds(),
            diagnostics=diagnostics,
            session_warnings=session_warnings,
        )

    x = {}
    open_vars = {}

    for s in sessions:
        for v in eligibility[s.id]:
            cap = v.effective_capacity
            x[(s.id, v.id)] = model.NewIntVar(0, cap, f"x_{s.id}_{v.id}")

    for v in venues:
        open_vars[v.id] = model.NewBoolVar(f"open_{v.id}")

    for s in sessions:
        vars_ = [x[(s.id, v.id)] for v in eligibility[s.id]]
        if not vars_:
            continue
        demand = s.expected_candidates
        for v in eligibility[s.id]:
            b = model.NewBoolVar(f"used_{s.id}_{v.id}")
            model.Add(x[(s.id, v.id)] > 0).OnlyEnforceIf(b)
            model.Add(x[(s.id, v.id)] == 0).OnlyEnforceIf(b.Not())
            model.AddImplication(b, open_vars[v.id])

        if allow_under_capacity:
            model.Add(sum(vars_) <= demand)
            slack = model.NewIntVar(0, demand, f"slack_{s.id}")
            model.Add(sum(vars_) + slack == demand)
        else:
            model.Add(sum(vars_) == demand)

    for i, s1 in enumerate(sessions):
        for s2 in sessions[i + 1:]:
            st1, en1 = session_interval(s1)
            st2, en2 = session_interval(s2)
            if not overlaps(st1, en1, st2, en2):
                continue
            shared = set(v.id for v in eligibility[s1.id]) & \
                     set(v.id for v in eligibility[s2.id])
            for vid in shared:
                b1 = model.NewBoolVar(f"b_{s1.id}_{vid}")
                b2 = model.NewBoolVar(f"b_{s2.id}_{vid}")
                model.Add(x[(s1.id, vid)] > 0).OnlyEnforceIf(b1)
                model.Add(x[(s1.id, vid)] == 0).OnlyEnforceIf(b1.Not())
                model.Add(x[(s2.id, vid)] > 0).OnlyEnforceIf(b2)
                model.Add(x[(s2.id, vid)] == 0).OnlyEnforceIf(b2.Not())
                model.AddBoolOr([b1.Not(), b2.Not()])

    objective_terms = []

    for v in venues:
        objective_terms.append(1000 * open_vars[v.id])

    for s in sessions:
        demand = s.expected_candidates
        for v in eligibility[s.id]:
            cap = v.effective_capacity
            waste = max(cap - demand, 0)
            b = model.NewBoolVar(f"used2_{s.id}_{v.id}")
            model.Add(x[(s.id, v.id)] > 0).OnlyEnforceIf(b)
            model.Add(x[(s.id, v.id)] == 0).OnlyEnforceIf(b.Not())
            objective_terms.append(waste * b)
            objective_terms.append(5 * b)

    model.Minimize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max_time_seconds
    solver.parameters.num_search_workers = 4
    status = solver.Solve(model)

    wall = (datetime.utcnow() - started).total_seconds()

    if status == cp_model.OPTIMAL:
        status_str = "optimal"
    elif status == cp_model.FEASIBLE:
        status_str = "feasible"
    elif status == cp_model.INFEASIBLE:
        diagnostics.append("CP-SAT proved the venue constraint set is unsatisfiable.")
        return VenueAllocationResult(
            status="infeasible", wall_time=wall,
            diagnostics=diagnostics, session_warnings=session_warnings)
    else:
        diagnostics.append("Solver could not determine a valid outcome within time limit.")
        return VenueAllocationResult(
            status="unknown", wall_time=wall,
            diagnostics=diagnostics, session_warnings=session_warnings)

    assignments = {}
    for s in sessions:
        row = {}
        total_assigned = 0
        for v in eligibility[s.id]:
            val = solver.Value(x[(s.id, v.id)])
            if val > 0:
                row[v.id] = val
                total_assigned += val
        assignments[s.id] = row
        if total_assigned < s.expected_candidates:
            session_warnings[s.id] = (
                f"Only {total_assigned}/{s.expected_candidates} candidates seated."
            )

    return VenueAllocationResult(
        status=status_str,
        wall_time=wall,
        objective=solver.ObjectiveValue(),
        assignments=assignments,
        diagnostics=diagnostics,
        session_warnings=session_warnings,
    )
"""
Invigilator assignment via CP-SAT.

Decision variable: y[s, i] ∈ {0,1}
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ortools.sat.python import cp_model

from ..models.invigilator import Invigilator
from .conflict_detector import (
    invigilator_eligible_for_session, session_interval, overlaps,
)


@dataclass
class InvigilatorAllocationResult:
    status: str
    wall_time: float
    objective: Optional[float] = None
    assignments: dict = field(default_factory=dict)
    diagnostics: list = field(default_factory=list)
    session_warnings: dict = field(default_factory=dict)


def solve_invigilator_allocation(sessions,
                                 invigilators,
                                 max_time_seconds: int = 30,
                                 fairness_weight: int = 1):
    started = datetime.utcnow()
    model = cp_model.CpModel()
    diagnostics = []
    warnings = {}

    eligible = {}
    for s in sessions:
        cands = []
        reasons = {}
        for i in invigilators:
            ok, reason = invigilator_eligible_for_session(i, s)
            if ok:
                cands.append(i)
            else:
                reasons[i.id] = reason
        eligible[s.id] = cands
        if len(cands) < s.required_invigilators:
            diagnostics.append(
                f"Session {s.id} ({s.examination.title}) needs "
                f"{s.required_invigilators} invigilator(s) but only "
                f"{len(cands)} eligible."
            )
            warnings[s.id] = "insufficient eligible invigilators"
            for inv in invigilators:
                r = reasons.get(inv.id)
                if r:
                    diagnostics.append(
                        f"  - {inv.staff_number} excluded: {r}")

    if any(len(eligible[s.id]) < s.required_invigilators for s in sessions):
        return InvigilatorAllocationResult(
            status="infeasible",
            wall_time=(datetime.utcnow() - started).total_seconds(),
            diagnostics=diagnostics,
            session_warnings=warnings,
        )

    y = {}
    for s in sessions:
        for i in eligible[s.id]:
            y[(s.id, i.id)] = model.NewBoolVar(f"y_{s.id}_{i.id}")

    for s in sessions:
        vars_ = [y[(s.id, i.id)] for i in eligible[s.id]]
        model.Add(sum(vars_) == s.required_invigilators)

    for i, s1 in enumerate(sessions):
        for s2 in sessions[i + 1:]:
            st1, en1 = session_interval(s1)
            st2, en2 = session_interval(s2)
            if not overlaps(st1, en1, st2, en2):
                continue
            for inv in invigilators:
                k1 = (s1.id, inv.id)
                k2 = (s2.id, inv.id)
                if k1 in y and k2 in y:
                    model.Add(y[k1] + y[k2] <= 1)

    baseline = {}
    for inv in invigilators:
        existing = 0
        for a in inv.assignments:
            if a.session in sessions:
                continue
            existing += 1
        baseline[inv.id] = existing

    max_load = model.NewIntVar(0, 1000, "max_load")
    for inv in invigilators:
        terms = [y[(s.id, inv.id)] for s in sessions if (s.id, inv.id) in y]
        lv = model.NewIntVar(0, 1000, f"load_{inv.id}")
        model.Add(lv == baseline[inv.id] + sum(terms))
        model.Add(lv <= max_load)

    objective_terms = [100 * max_load]
    for inv in invigilators:
        for s in sessions:
            if (s.id, inv.id) in y:
                objective_terms.append(fairness_weight * y[(s.id, inv.id)])

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
        return InvigilatorAllocationResult(
            status="infeasible", wall_time=wall,
            diagnostics=diagnostics + [
                "CP-SAT proved invigilator constraints unsatisfiable."],
            session_warnings=warnings)
    else:
        return InvigilatorAllocationResult(
            status="unknown", wall_time=wall,
            diagnostics=diagnostics + [
                "Solver hit time limit without a proven result."],
            session_warnings=warnings)

    assignments = {}
    for s in sessions:
        row = [i.id for i in eligible[s.id]
               if solver.Value(y[(s.id, i.id)])]
        assignments[s.id] = row
        if len(row) < s.required_invigilators:
            warnings[s.id] = "assigned below required number"

    return InvigilatorAllocationResult(
        status=status_str, wall_time=wall,
        objective=solver.ObjectiveValue(),
        assignments=assignments, diagnostics=diagnostics,
        session_warnings=warnings,
    )
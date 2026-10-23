"""
End-to-end solver orchestrator.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..models.venue import Venue
from ..models.invigilator import Invigilator
from ..models.examination import ExaminationSession
from .venue_allocator import solve_venue_allocation, VenueAllocationResult
from .invigilator_allocator import (solve_invigilator_allocation,
                                    InvigilatorAllocationResult)


@dataclass
class SolverOutcome:
    status: str
    wall_time: float
    objective: Optional[float]
    venue_result: VenueAllocationResult
    invigilator_result: Optional[InvigilatorAllocationResult]
    diagnostics: list = field(default_factory=list)
    session_warnings: dict = field(default_factory=dict)

    @property
    def combined_assignments(self) -> dict:
        out = {}
        for sid, venues in self.venue_result.assignments.items():
            out[sid] = {"venues": venues, "invigilators": []}
        if self.invigilator_result:
            for sid, invs in self.invigilator_result.assignments.items():
                out.setdefault(sid, {"venues": {}, "invigilators": []})
                out[sid]["invigilators"] = invs
        return out


def run_full_allocation(exam_period: str,
                        start_date=None,
                        end_date=None,
                        max_time_seconds: int = 30) -> SolverOutcome:
    started = datetime.utcnow()

    q = (ExaminationSession.query
         .join(ExaminationSession.examination)
         .filter(ExaminationSession.status != "cancelled",
                 ExaminationSession.examination.has(
                     exam_period=exam_period)))
    if start_date:
        q = q.filter(ExaminationSession.exam_date >= start_date)
    if end_date:
        q = q.filter(ExaminationSession.exam_date <= end_date)
    sessions = q.order_by(ExaminationSession.exam_date,
                          ExaminationSession.start_time).all()

    venues = (Venue.query.filter_by(status="available")
              .order_by(Venue.capacity).all())
    invigilators = Invigilator.query.filter_by(is_active=True).all()

    diagnostics = []
    if not sessions:
        return SolverOutcome(
            status="infeasible", wall_time=0.0, objective=None,
            venue_result=VenueAllocationResult(
                status="infeasible", wall_time=0.0,
                diagnostics=["No sessions to allocate."]),
            invigilator_result=None,
            diagnostics=["No sessions to allocate for the given period."],
        )
    if not venues:
        diagnostics.append("No available venues.")
    if not invigilators:
        diagnostics.append("No active invigilators.")

    venue_result = solve_venue_allocation(
        sessions=sessions, venues=venues,
        max_time_seconds=max_time_seconds)
    diagnostics.extend(venue_result.diagnostics)

    if venue_result.status in ("infeasible", "unknown"):
        return SolverOutcome(
            status=venue_result.status,
            wall_time=(datetime.utcnow() - started).total_seconds(),
            objective=venue_result.objective,
            venue_result=venue_result,
            invigilator_result=None,
            diagnostics=diagnostics,
            session_warnings=dict(venue_result.session_warnings),
        )

    inv_result = solve_invigilator_allocation(
        sessions=sessions, invigilators=invigilators,
        max_time_seconds=max_time_seconds)
    diagnostics.extend(inv_result.diagnostics)

    statuses = {venue_result.status, inv_result.status}
    if "infeasible" in statuses:
        final = "infeasible"
    elif "unknown" in statuses:
        final = "unknown"
    elif statuses == {"optimal"}:
        final = "optimal"
    else:
        final = "feasible"

    warnings = dict(venue_result.session_warnings)
    warnings.update({k: v for k, v in inv_result.session_warnings.items()
                     if k not in warnings})

    return SolverOutcome(
        status=final,
        wall_time=(datetime.utcnow() - started).total_seconds(),
        objective=(venue_result.objective or 0) + (inv_result.objective or 0),
        venue_result=venue_result,
        invigilator_result=inv_result,
        diagnostics=diagnostics,
        session_warnings=warnings,
    )
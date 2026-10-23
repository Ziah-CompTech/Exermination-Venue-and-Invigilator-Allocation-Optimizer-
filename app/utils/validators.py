from datetime import datetime, date, time
from wtforms.validators import ValidationError


def validate_time_range(start: time, end: time,
                        duration_minutes: int | None = None):
    if end <= start:
        raise ValidationError("End time must be after start time.")
    if duration_minutes is not None:
        actual = (datetime.combine(date.today(), end) -
                  datetime.combine(date.today(), start)).seconds // 60
        if abs(actual - duration_minutes) > 1:
            raise ValidationError(
                f"Duration ({duration_minutes} min) does not match start/end times."
            )


def parse_time(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def overlaps(a_start, a_end, b_start, b_end) -> bool:
    """True when two time intervals overlap (endpoints exclusive)."""
    return a_start < b_end and b_start < a_end
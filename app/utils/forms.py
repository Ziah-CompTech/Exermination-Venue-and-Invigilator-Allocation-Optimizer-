"""Reusable WTForms fields and helpers."""
from wtforms import SelectField


def choices_from_query(items, id_attr="id", label_attr="name", blank=True):
    out = [(str(getattr(i, id_attr)), getattr(i, label_attr)) for i in items]
    if blank:
        out = [("", "— select —")] + out
    return out


def coerce_int(value):
    try:
        return int(value) if value not in (None, "", "None") else None
    except (TypeError, ValueError):
        return None


class IntSelectField(SelectField):
    coerce = staticmethod(coerce_int)
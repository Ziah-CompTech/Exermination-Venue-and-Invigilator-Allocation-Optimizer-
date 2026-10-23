"""
CSV and PDF exporters built on top of report_service providers.
"""
import csv
import io
from datetime import datetime

from flask import current_app, Response
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                Paragraph, Spacer)


def csv_response(filename, headers, rows):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(headers)
    for r in rows:
        w.writerow(r)
    return Response(
        out.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def pdf_response(filename, title, headers, rows, landscape_mode=True):
    from ..models.allocation import InstitutionSettings

    buf = io.BytesIO()
    pagesize = landscape(A4) if landscape_mode else A4
    doc = SimpleDocTemplate(
        buf, pagesize=pagesize,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
        title=title)
    styles = getSampleStyleSheet()
    h_style = ParagraphStyle("H", parent=styles["Heading1"], fontSize=15,
                             textColor=colors.HexColor("#0b2b52"))
    meta_style = ParagraphStyle("M", parent=styles["Normal"], fontSize=9,
                                textColor=colors.grey)
    cell_style = ParagraphStyle("C", parent=styles["Normal"], fontSize=8,
                                leading=10)

    try:
        inst_name = InstitutionSettings.get().institution_name
    except Exception:
        inst_name = current_app.config.get("INSTITUTION_NAME", "Institution")

    story = []
    story.append(Paragraph(inst_name, h_style))
    story.append(Paragraph(title, styles["Heading3"]))
    story.append(Paragraph(
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        meta_style))
    story.append(Spacer(1, 6))

    if not rows:
        story.append(Paragraph("No data available for this report.",
                               cell_style))
    else:
        table_data = [[Paragraph(str(h), cell_style) for h in headers]]
        for r in rows:
            table_data.append(
                [Paragraph("" if v is None else str(v), cell_style)
                 for v in r])
        col_count = len(headers)
        avail = pagesize[0] - 30 * mm
        col_width = avail / col_count
        t = Table(table_data, colWidths=[col_width] * col_count,
                  repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b2b52")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#f5f7fb")]),
        ]))
        story.append(t)

    doc.build(story)
    buf.seek(0)
    return Response(
        buf.read(), mimetype="application/pdf",
        headers={"Content-Disposition":
                 f"attachment; filename={filename}"})
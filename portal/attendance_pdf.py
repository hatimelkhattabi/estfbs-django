"""Private presence lists generated from the existing student registry."""

from html import escape
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from .vehicle_documents import document_fonts
from .attendance_cohorts import YEAR_LABELS, year_number


def attendance_pdf(students, data, teacher):
    regular, bold = document_fonts()
    width, height = A4
    available = width - 72
    text = ParagraphStyle("AttendanceText", fontName=regular, fontSize=10, leading=14)
    title = ParagraphStyle(
        "AttendanceTitle",
        parent=text,
        fontName=bold,
        fontSize=18,
        leading=24,
        textColor=colors.HexColor("#112c4c"),
    )
    lines = [
        Paragraph("École Supérieure de Technologie de Fkih Ben Salah", text),
        Paragraph("LISTE DE PRÉSENCE", title),
        Paragraph(
            escape(data["filiere"])
            + " · "
            + YEAR_LABELS[year_number(data["niveau"])]
            + " · "
            + escape(data["annee_universitaire"]),
            text,
        ),
        Paragraph("Enseignant : " + escape(teacher.nom_complet), text),
        Paragraph("Effectif : " + str(len(students)), text),
    ]
    sizes = [line.wrap(available, height)[1] for line in lines]
    top = 30 + sum(sizes) + 22

    def header(canvas, doc):
        canvas.saveState()
        y = height - 30
        for paragraph, h in zip(lines, sizes):
            paragraph.drawOn(canvas, 36, y - h)
            y -= h
        canvas.setStrokeColor(colors.HexColor("#c4a15c"))
        canvas.line(36, y - 9, width - 36, y - 9)
        canvas.setFont(regular, 9)
        canvas.setFillColor(colors.HexColor("#64758a"))
        canvas.drawString(36, 22, "EST-FBS · Liste de présence")
        canvas.drawRightString(width - 36, 22, "Page " + str(doc.page))
        canvas.restoreState()

    rows = [["N°", "Apogée", "Nom et prénom", "Signature"]]
    for index, student in enumerate(students, 1):
        rows.append(
            [
                str(index),
                Paragraph(escape(student.apogee), text),
                Paragraph(escape(student.nom + " " + student.prenom), text),
                "",
            ]
        )
    table = Table(
        rows,
        colWidths=[30, 85, available - 245, 130],
        repeatRows=1,
        minRowHeights=[30] * len(rows),
    )
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), regular),
                ("FONTNAME", (0, 0), (-1, 0), bold),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#112c4c")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd7e4")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f6f8fb")],
                ),
            ]
        )
    )
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=top,
        bottomMargin=40,
        title="Liste de présence EST-FBS",
        author="EST-FBS",
    )
    doc.build([table], onFirstPage=header, onLaterPages=header)
    return buffer.getvalue()

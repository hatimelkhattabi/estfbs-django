"""Landscape presence PDFs using the cells and styles of the supplied Excel sheet."""

from html import escape
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Table, TableStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from .attendance_excel import open_source, identifier
from .vehicle_documents import document_fonts


def _color(color, fallback=colors.black):
    if color and color.type == "rgb" and isinstance(color.rgb, str):
        return colors.HexColor("#" + color.rgb[-6:])
    return fallback


def excel_presence_pdf(source, teacher):
    book = open_source(source.path, read_only=False)
    try:
        sheet = book[source.sheet_name]
        regular, bold = document_fonts()
        page_width, page_height = landscape(A4)
        # The supplied registers use A:M: identity columns and ten sessions.
        columns = 13
        widths = []
        for index in range(1, columns + 1):
            width = sheet.sheet_format.defaultColWidth or 10
            for dimension in sheet.column_dimensions.values():
                if dimension.min <= index <= dimension.max:
                    width = dimension.width
                    break
            widths.append((width * 7 + 5) * 0.75)
        scale = (page_width - 36) / sum(widths)
        widths = [w * scale for w in widths]
        # Keep Apogée identifiers on one line at a readable size. Take the
        # additional room from the ten empty attendance columns equally.
        extra = max(0, 70 - widths[0])
        widths[0] += extra
        for index in range(3, columns):
            widths[index] -= extra / 10
        spans = [
            ((r.min_col - 1, r.min_row - 1), (r.max_col - 1, r.max_row - 1))
            for r in sheet.merged_cells.ranges
            if r.max_col <= columns
        ]
        # Reserve the same two logo areas as in the source's first two rows.
        logo_spans = [((0, 0), (1, 1)), ((11, 0), (12, 1))]
        spans += [s for s in logo_spans if s not in spans]
        span_by_start = {start: end for start, end in spans}
        covered = {
            (col, row)
            for (c1, r1), (c2, r2) in spans
            for row in range(r1, r2 + 1)
            for col in range(c1, c2 + 1)
            if (col, row) != (c1, r1)
        }
        row_heights = [
            max(
                15,
                (sheet.row_dimensions[r].height or sheet.sheet_format.defaultRowHeight)
                * min(scale, 1.15),
            )
            for r in range(1, sheet.max_row + 1)
        ]
        rows, commands = [], [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]
        for row_index in range(sheet.max_row):
            row = []
            for col_index in range(columns):
                cell = sheet.cell(row_index + 1, col_index + 1)
                if (col_index, row_index) in covered:
                    row.append("")
                    continue
                value = (
                    teacher.nom_complet
                    if (row_index, col_index) == (3, 2)
                    else cell.value
                )
                value = identifier(value)
                font_size = min(float(cell.font.sz or 11), 13)
                end_col, end_row = span_by_start.get(
                    (col_index, row_index), (col_index, row_index)
                )
                font_name = bold if cell.font.b else regular
                cell_width = sum(widths[col_index : end_col + 1]) - 6
                if 5 <= row_index <= 10 and value and "\n" not in value:
                    text_width = stringWidth(value, font_name, font_size)
                    if text_width > cell_width:
                        font_size = max(7, font_size * cell_width / text_width * .97)
                if row_index >= 11 and col_index in (1, 2) and value:
                    longest = max(stringWidth(word, font_name, font_size) for word in value.split())
                    if longest > cell_width:
                        font_size = max(8, font_size * cell_width / longest * .97)
                alignment = {"center": 1, "right": 2}.get(cell.alignment.horizontal, 0)
                style = ParagraphStyle(
                    "Cell",
                    fontName=font_name,
                    fontSize=font_size,
                    leading=font_size * 1.12,
                    textColor=_color(cell.font.color),
                    alignment=alignment,
                )
                paragraph = Paragraph(escape(value).replace("\n", "<br/>"), style)
                end_col, end_row = span_by_start.get(
                    (col_index, row_index), (col_index, row_index)
                )
                height = (
                    paragraph.wrap(sum(widths[col_index : end_col + 1]) - 6, 1000)[1]
                    + 4
                )
                if end_row == row_index:
                    row_heights[row_index] = max(row_heights[row_index], height)
                row.append(paragraph)
                if cell.fill.patternType == "solid":
                    commands.append(
                        (
                            "BACKGROUND",
                            (col_index, row_index),
                            (end_col, end_row),
                            _color(cell.fill.fgColor, colors.white),
                        )
                    )
                for side, command in [
                    ("left", "LINEBEFORE"),
                    ("right", "LINEAFTER"),
                    ("top", "LINEABOVE"),
                    ("bottom", "LINEBELOW"),
                ]:
                    border = getattr(cell.border, side)
                    if border and border.style:
                        weight = 0.8 if border.style in {"medium", "thick"} else 0.4
                        commands.append(
                            (
                                command,
                                (col_index, row_index),
                                (end_col, end_row),
                                weight,
                                _color(border.color),
                            )
                        )
            rows.append(row)
        # Embedded source logos are read, not rewritten into the workbook.
        for image, col in zip(sheet._images[:2], [0, 11]):
            data = image._data()
            max_width, max_height = (
                sum(widths[col : col + 2]) - 8,
                sum(row_heights[:2]) - 4,
            )
            ratio = min(max_width / image.width, max_height / image.height)
            rows[0][col] = Image(
                io.BytesIO(data),
                width=image.width * ratio,
                height=image.height * ratio,
                hAlign="CENTER",
            )
        for start, end in spans:
            commands.append(("SPAN", start, end))
        table = Table(rows, colWidths=widths, rowHeights=row_heights, repeatRows=11)
        table.setStyle(TableStyle(commands))
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=(page_width, page_height),
            leftMargin=18,
            rightMargin=18,
            topMargin=16,
            bottomMargin=24,
            title=f"Liste de présence - {source.filiere} - {source.annee_universitaire}",
            author="EST-FBS",
        )

        def footer(canvas, document):
            canvas.setFont(regular, 8)
            canvas.drawRightString(page_width - 18, 10, "Page " + str(document.page))

        doc.build([table], onFirstPage=footer, onLaterPages=footer)
        return buffer.getvalue()
    finally:
        book.close()

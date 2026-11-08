"""PDF adapter for the supplied vehicle templates, using ReportLab on Windows.

Text, tables and mission field coordinates come from the Jinja versions of the
original views. No PHP runtime or additional PDF package is required.
"""

from dataclasses import dataclass, field
from html import escape
from html.parser import HTMLParser
import re

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.template.loader import render_to_string
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from .vehicles import professor_name


@dataclass
class Element:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)

    def find(self, class_name):
        for child in self.children:
            if isinstance(child, Element):
                if class_name in child.attrs.get("class", "").split():
                    return child
                found = child.find(class_name)
                if found is not None:
                    return found
        return None

    def all(self, tag):
        result = []
        for child in self.children:
            if isinstance(child, Element):
                if child.tag == tag:
                    result.append(child)
                else:
                    result.extend(child.all(tag))
        return result

    def text(self):
        return re.sub(
            r"\s+",
            " ",
            " ".join(c.text() if isinstance(c, Element) else c for c in self.children),
        ).strip()

    def markup(self):
        result = []
        for child in self.children:
            if isinstance(child, str):
                result.append(escape(child))
            elif child.tag == "br":
                result.append("<br/>")
            elif child.tag in {"strong", "b", "em", "i"}:
                tag = {"strong": "b", "em": "i"}.get(child.tag, child.tag)
                result.append(f"<{tag}>{child.markup()}</{tag}>")
            else:
                result.append(child.markup())
        return "".join(result)


class DocumentParser(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Element("root")
        self.stack = [self.root]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        element = Element(tag, dict(attrs))
        self.stack[-1].children.append(element)
        if tag not in {"img", "meta", "link", "br", "hr", "input"}:
            self.stack.append(element)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def document_context(obj):
    mission = (
        obj.motif_visite.strip()
        or "Encadrement de visite pédagogique et mission scientifique"
    )
    if obj.filiere:
        mission += " — Filière : " + obj.filiere
    return {
        "demande": obj,
        "professor_name": professor_name(obj.nom_professeur),
        "logoEst": str(settings.BASE_DIR / "static/assets/img/logo-est.jpg"),
        "logoUsms": str(settings.BASE_DIR / "static/assets/img/logo-usms.png"),
        "ordreMissionBg": (
            str(settings.BASE_DIR / "portal/assets/ordre-de-mission-template.png")
            if obj.ordre_mission_disponible
            else None
        ),
        "nomComplet": obj.nom_professeur.strip(),
        "gradeText": obj.grade_professeur.strip() or "PES",
        "missionText": mission,
        "dateDepartText": obj.date_visite.strftime("%d/%m/%Y")
        + (" à " + obj.heure_depart if obj.heure_depart else ""),
        "dateRetourText": obj.date_retour_prevue.strftime("%d/%m/%Y")
        + (" à " + obj.heure_retour if obj.heure_retour else ""),
        "transportText": obj.type_vehicule or "Véhicule de service EST-FBS",
        "personnelText": " + ".join(
            filter(
                None,
                [
                    obj.accompagnateurs.strip(),
                    (
                        f"{obj.effectif_etudiants} étudiant(s)"
                        if obj.effectif_etudiants
                        else ""
                    ),
                ],
            )
        )
        or "Néant",
        "presenteraText": obj.organisme_accueil or obj.destination,
        "dateFaitText": timezone.localtime(obj.date_demande).strftime("%d/%m/%Y"),
    }


def document_tree(obj, name):
    if name == "ordre-mission-pdf" and not obj.ordre_mission_disponible:
        raise PermissionDenied(
            "L’ordre de mission nécessite la validation de l’administration."
        )
    html = render_to_string(
        "vehicule/" + name + ".html", document_context(obj), using="site"
    )
    return DocumentParser(html).root


def document_fonts():
    for name, filename in [
        ("DejaVuSans", "DejaVuSans.ttf"),
        ("DejaVuSans-Bold", "DejaVuSans-Bold.ttf"),
    ]:
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(
                TTFont(name, str(settings.BASE_DIR / "static/fonts" / filename))
            )
    pdfmetrics.registerFontFamily(
        "DejaVuSans",
        normal="DejaVuSans",
        bold="DejaVuSans-Bold",
        italic="DejaVuSans",
        boldItalic="DejaVuSans-Bold",
    )
    return "DejaVuSans", "DejaVuSans-Bold"


def request_story(obj):
    root = document_tree(obj, "pdf").find("page-demande")
    font, bold = document_fonts()
    width = A4[0] - 80
    blue = colors.HexColor("#1e3a8a")
    style = ParagraphStyle(
        "VehicleCell",
        fontName=font,
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
    )

    def paragraph(element, **options):
        if isinstance(element, Element) and element.tag == "th":
            options.setdefault("fontName", bold)
            options.setdefault("textColor", colors.HexColor("#334155"))
        if (
            isinstance(element, Element)
            and "highlight-val" in element.attrs.get("class", "").split()
        ):
            options.setdefault("fontName", bold)
            options.setdefault("textColor", blue)
        content = (
            element.markup() if isinstance(element, Element) else escape(str(element))
        )
        return Paragraph(
            content, ParagraphStyle("VehicleText", parent=style, **options)
        )

    header = root.find("header-table")
    center = header.find("header-center")
    header_lines = []
    for element in center.children:
        if isinstance(element, Element):
            size = 10 if "title-royaume" in element.attrs.get("class", "") else 8
            header_lines.append(
                paragraph(
                    element, alignment=1, fontSize=size, leading=11, textColor=blue
                )
            )
    logo_images = []
    for element in header.all("img"):
        image = Image(element.attrs["src"])
        ratio = min(60 / image.imageWidth, 59 / image.imageHeight)
        image.drawWidth = image.imageWidth * ratio
        image.drawHeight = image.imageHeight * ratio
        logo_images.append(image)
    header_table = Table(
        [[logo_images[0], header_lines, logo_images[1]]],
        colWidths=[66, width - 132, 66],
    )
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LINEBELOW", (0, 0), (-1, -1), 1.5, blue),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    title = Table(
        [
            [
                paragraph(
                    root.find("doc-title"),
                    fontName=bold,
                    fontSize=12.5,
                    leading=16,
                    alignment=1,
                    textColor=blue,
                )
            ],
            [
                paragraph(
                    root.find("doc-subtitle"), fontSize=8.5, leading=11, alignment=1
                )
            ],
        ],
        colWidths=[width],
    )
    title.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, blue),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
            ]
        )
    )
    meta = root.find("meta-table").all("td")
    metadata = Table(
        [
            [
                paragraph(meta[0], fontSize=8, leading=12),
                paragraph(
                    meta[1],
                    fontSize=8,
                    leading=12,
                    alignment=2,
                    textColor=colors.HexColor("#92400e"),
                ),
            ]
        ],
        colWidths=[width * 0.57, width * 0.43],
    )
    story = [header_table, Spacer(1, 10), title, Spacer(1, 8), metadata, Spacer(1, 4)]
    pending_heading = None
    for element in root.children:
        if not isinstance(element, Element):
            continue
        classes = element.attrs.get("class", "").split()
        if "section-title" in classes:
            pending_heading = Table(
                [
                    [
                        paragraph(
                            element,
                            fontName=bold,
                            fontSize=8.5,
                            leading=11,
                            textColor=colors.white,
                        )
                    ]
                ],
                colWidths=[width],
            )
            pending_heading.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), blue),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
        elif "info-table" in classes:
            rows = [
                [
                    paragraph(cell)
                    for cell in row.children
                    if isinstance(cell, Element) and cell.tag in {"th", "td"}
                ]
                for row in element.all("tr")
            ]
            table = Table(
                rows,
                colWidths=[width * 0.28, width * 0.72],
                hAlign="CENTER",
                splitInRow=1,
            )
            table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#cbd5e1")),
                        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ]
                )
            )
            story.extend([pending_heading, Spacer(1, 4), table, Spacer(1, 6)])
            pending_heading = None
        elif "signature-table" in classes:
            cells = []
            for cell in element.all("td"):
                cells.append(
                    [
                        paragraph(
                            cell.find("sign-title"),
                            fontName=bold,
                            fontSize=7.5,
                            leading=10,
                            alignment=1,
                            textColor=blue,
                        ),
                        Spacer(1, 24),
                        paragraph(
                            cell.find("sign-sub"),
                            fontSize=7,
                            leading=10,
                            alignment=1,
                            textColor=colors.HexColor("#64748b"),
                        ),
                    ]
                )
            table = Table([cells], colWidths=[width / 3] * 3)
            table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fbfcfe")),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.append(KeepTogether([pending_heading, Spacer(1, 4), table]))
            pending_heading = None
        elif element.tag == "div" and "Remarque importante" in element.text():
            notice = Table(
                [
                    [
                        paragraph(
                            element,
                            fontSize=7.5,
                            leading=10,
                            textColor=colors.HexColor("#64748b"),
                        )
                    ]
                ],
                colWidths=[width],
            )
            notice.setStyle(
                TableStyle(
                    [
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.extend([Spacer(1, 8), notice])
    return story


def mission_story(obj):
    root = document_tree(obj, "ordre-mission-pdf").find("page-container")
    font, bold = document_fonts()
    width, height = A4
    prepared, overflow = [], []
    names = [
        "Nom",
        "Grade",
        "Mission",
        "Destination",
        "Date de départ",
        "Date de retour",
        "Transport",
        "Personnel de la mission",
        "Organisme d’accueil",
        "Date",
    ]
    elements = [
        e
        for e in root.children
        if isinstance(e, Element) and "field" in e.attrs.get("class", "").split()
    ]
    for label, element in zip(names, elements, strict=True):
        positions = {
            key: float(value) / 100
            for key, value in re.findall(
                r"(top|left|width):\s*([\d.]+)%", element.attrs["style"]
            )
        }
        area_height = (
            0.105
            if label == "Mission"
            else (0.035 if label in {"Destination", "Organisme d’accueil"} else 0.03)
        ) * height
        for size in (11, 10, 9, 8, 7):
            style = ParagraphStyle(
                "MissionField", fontName=bold, fontSize=size, leading=size * 1.2
            )
            para = Paragraph(element.markup(), style)
            _, para_height = para.wrap(positions["width"] * width, area_height)
            if para_height <= area_height:
                break
        else:
            overflow.append((label, element.markup()))
            para = Paragraph("Voir l’annexe jointe : " + escape(label), style)
            _, para_height = para.wrap(positions["width"] * width, area_height)
        prepared.append(
            (
                para,
                positions["left"] * width,
                height * (1 - positions["top"]) - para_height,
            )
        )
    reference = root.find("ref-number").text()
    background = root.find("bg-template").attrs["src"]

    class MissionPage(Flowable):
        def __init__(self):
            super().__init__()
            self.width = self.height = 1

        def draw(self):
            canvas = self.canv
            x, y = canvas.absolutePosition(0, 0)
            canvas.saveState()
            canvas.translate(-x, -y)
            canvas.drawImage(background, 0, 0, width=width, height=height, mask="auto")
            canvas.setFont(bold, 8)
            canvas.setFillColor(colors.HexColor("#334155"))
            canvas.drawCentredString(width / 2, height * (1 - 0.244) - 8, reference)
            for paragraph, left, bottom in prepared:
                paragraph.drawOn(canvas, left, bottom)
            canvas.restoreState()

    story = [MissionPage()]
    if overflow:
        style = ParagraphStyle(
            "MissionAnnex", fontName=font, fontSize=10, leading=14, spaceAfter=12
        )
        story += [
            PageBreak(),
            Paragraph("Annexe à l’ordre de mission", style),
            Paragraph(escape(obj.code_suivi), style),
        ]
        for label, markup in overflow:
            story += [Paragraph(escape(label), style), Paragraph(markup, style)]
    return story

import io

from reportlab.lib.pagesizes import A4
from reportlab.platypus import PageBreak, SimpleDocTemplate

from .vehicle_documents import mission_story, request_story


def build_pdf(story):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=30, bottomMargin=30
    )
    doc.build(story)
    return buf.getvalue()


def vehicle_pdf(obj):
    story = request_story(obj)
    if obj.ordre_mission_disponible:
        story += [PageBreak()] + mission_story(obj)
    return build_pdf(story)


def mission_pdf(obj):
    return build_pdf(mission_story(obj))

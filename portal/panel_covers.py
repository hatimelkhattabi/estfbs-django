"""Validation de la composition Canvas. Les chemins de fichiers viennent du serveur."""

import math
import re
from django.core.exceptions import ValidationError


def clean_design(value):
    def fail():
        raise ValidationError(
            "La composition du visuel est invalide. Vérifiez les textes et les réglages."
        )

    def number(v, low, high):
        if (
            isinstance(v, bool)
            or not isinstance(v, (float, int))
            or not math.isfinite(v)
            or not low <= v <= high
        ):
            fail()
        return v

    def color(v):
        if not isinstance(v, str) or not re.fullmatch("#[a-fA-F0-9]{6}", v):
            fail()
        return v

    if not isinstance(value, dict) or value.get("version") != 1:
        fail()
    if value.get("background") not in ("genie-civil", "plain", "custom"):
        fail()
    logo = value.get("logo")
    texts = value.get("texts")
    if (
        not isinstance(logo, dict)
        or type(logo.get("visible")) is not bool
        or logo.get("source") not in ("default", "custom")
    ):
        fail()
    if not isinstance(texts, list) or len(texts) > 8:
        fail()
    output = {
        "version": 1,
        "background": value["background"],
        "backgroundColor": color(value.get("backgroundColor")),
        "veil": number(value.get("veil"), 0, 95),
        "cropX": number(value.get("cropX"), 0, 100),
        "cropY": number(value.get("cropY"), 0, 100),
        "logo": {
            "visible": logo["visible"],
            "source": logo["source"],
            "x": number(logo.get("x"), 0, 100),
            "y": number(logo.get("y"), 0, 100),
            "width": number(logo.get("width"), 5, 35),
        },
        "texts": [],
    }
    ids = set()
    for text in texts:
        if not isinstance(text, dict):
            fail()
        key = text.get("id")
        label = text.get("text", "")
        if (
            not isinstance(key, str)
            or not re.fullmatch("text-[a-zA-Z0-9-]{1,50}", key)
            or key in ids
        ):
            fail()
        ids.add(key)
        if (
            not isinstance(label, str)
            or len(label) > 240
            or text.get("font") not in ("outfit", "sans", "serif")
            or text.get("align") not in ("left", "center", "right")
            or type(text.get("bold")) is not bool
        ):
            fail()
        output["texts"].append(
            {
                "id": key,
                "text": label,
                "x": number(text.get("x"), 0, 100),
                "y": number(text.get("y"), 0, 100),
                "size": number(text.get("size"), 18, 140),
                "width": number(text.get("width"), 15, 90),
                "font": text["font"],
                "bold": text["bold"],
                "color": color(text.get("color")),
                "align": text["align"],
            }
        )
    return output

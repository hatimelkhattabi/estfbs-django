"""Year labels shared by the attendance form, filtering and exported PDF."""

import re
import unicodedata

YEAR_CHOICES = [("1", "1re année"), ("2", "2e année"), ("3", "3e année")]
YEAR_LABELS = dict(YEAR_CHOICES)


def year_number(value):
    text = unicodedata.normalize("NFKD", str(value or "").strip().casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"\s+", " ", text)
    words = {"premiere annee": "1", "deuxieme annee": "2", "troisieme annee": "3"}
    if text in words:
        return words[text]
    match = re.fullmatch(
        r"(?:annee\s*)?([1-3])(?:\s*(?:ere|re|er|eme|e))?(?:\s*annee)?", text
    )
    return match[1] if match else None

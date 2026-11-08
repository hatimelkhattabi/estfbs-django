"""Read the supplied class workbooks without modifying the originals."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
import warnings
from django.conf import settings


@dataclass(frozen=True)
class ClassSheet:
    path: Path
    sheet_name: str
    filiere: str
    niveau: str
    annee_universitaire: str


@dataclass(frozen=True)
class ClassStudent:
    apogee: str
    nom: str
    prenom: str


def open_source(path, *, read_only=False):
    from openpyxl import load_workbook

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Cannot parse header or footer.*")
        return load_workbook(path, read_only=read_only, data_only=True)


@lru_cache(maxsize=4)
def _catalog(root, signature):
    records = []
    for filename, _, _ in signature:
        path = Path(root) / filename
        book = open_source(path)
        try:
            for sheet in book:
                title = str(sheet["A3"].value or "")
                match = re.search(
                    r"Filière\s+(.+?)\s+([1-3])(?:ère|re|ème|éme|e|eme|ere)?\s+ann[ée]e\s*[-–]\s*(\d{4}[-–]\d{4})\s*$",
                    title,
                    re.IGNORECASE,
                )
                if match:
                    records.append(
                        ClassSheet(
                            path,
                            sheet.title,
                            " ".join(match[1].split()),
                            match[2],
                            match[3].replace("–", "-"),
                        )
                    )
        finally:
            book.close()
    return tuple(records)


def attendance_sources():
    root = getattr(
        settings, "ATTENDANCE_SOURCE_ROOT", settings.BASE_DIR / "portal/assets/presence"
    )
    if root is None:
        return ()
    root = Path(root)
    if not root.is_dir():
        return ()
    files = sorted(root.glob("*.xlsx"))
    signature = tuple((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in files)
    return _catalog(str(root.resolve()), signature)


def source_for(data):
    return next(
        (
            s
            for s in attendance_sources()
            if all(
                getattr(s, k) == data[k]
                for k in ("filiere", "niveau", "annee_universitaire")
            )
        ),
        None,
    )


def identifier(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def source_students(source):
    book = open_source(source.path)
    try:
        sheet = book[source.sheet_name]
        return [
            ClassStudent(identifier(apogee), str(nom).strip(), str(prenom).strip())
            for apogee, nom, prenom in sheet.iter_rows(
                min_row=12, max_col=3, values_only=True
            )
            if nom is not None
            and prenom is not None
            and str(nom).strip()
            and str(prenom).strip()
        ]
    finally:
        book.close()

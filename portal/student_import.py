"""Lecture du classeur maître des étudiants, sans déduire un Apogée depuis un nom."""

from dataclasses import dataclass
from pathlib import Path
import math
import re
import unicodedata
import zipfile

from django.core.exceptions import ValidationError

from .models import Etudiant
from .validators import validate_apogee


class StudentImportError(ValueError):
    pass


def identity_key(value):
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def same_identity(student, values):
    return all(
        identity_key(getattr(student, field)) == identity_key(values[field])
        for field in ("nom", "prenom")
    )


def header_key(value):
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return re.sub(r"[^a-z0-9]", "", text)


def cell_text(cell):
    if cell is None or cell.value is None:
        return ""
    if cell.data_type == "f":
        raise StudentImportError(
            "Les colonnes d’identité doivent contenir des valeurs, pas des formules."
        )
    return str(cell.value).strip()


def apogee_text(cell):
    value = cell_text(cell)
    if not value:
        return ""
    original = cell.value
    if isinstance(original, bool):
        raise StudentImportError(
            "Un numéro Apogée ne peut pas être une valeur booléenne."
        )
    if isinstance(original, (int, float)):
        if isinstance(original, float) and (
            not math.isfinite(original) or not original.is_integer()
        ):
            raise StudentImportError(
                "Un numéro Apogée doit être un entier ou un texte composé de chiffres."
            )
        value = str(int(original))
        if re.fullmatch(r"0+", cell.number_format or ""):
            value = value.zfill(len(cell.number_format))
    elif re.fullmatch(r"[0-9]+\.0+", value):
        value = value.split(".")[0]
    try:
        validate_apogee(value)
    except ValidationError as exc:
        raise StudentImportError(
            "Le numéro Apogée doit contenir de 1 à 32 chiffres."
        ) from exc
    return value


@dataclass
class StudentImport:
    students: list
    missing_apogee: int
    duplicate_rows: int
    source_rows: int


def read_students(filename, sheet_name="Etudiants"):
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise StudentImportError(
            "Installez la dépendance avec : python -m pip install -r requirements-etudiants.txt"
        ) from exc

    path = Path(filename)
    if not path.is_file() or path.suffix.lower() != ".xlsx":
        raise StudentImportError("Choisissez un fichier Excel .xlsx existant.")
    if path.stat().st_size > 20 * 1024 * 1024:
        raise StudentImportError("Le classeur doit peser moins de 20 Mo.")
    try:
        with zipfile.ZipFile(path) as archive:
            if sum(info.file_size for info in archive.infolist()) > 250 * 1024 * 1024:
                raise StudentImportError(
                    "Le contenu décompressé du classeur est trop volumineux."
                )
        workbook = load_workbook(
            path, read_only=True, data_only=False, keep_links=False
        )
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        raise StudentImportError("Le fichier Excel ne peut pas être lu.") from exc
    try:
        if sheet_name not in workbook.sheetnames:
            raise StudentImportError(
                f"Feuille « {sheet_name} » introuvable. Utilisez le classeur fusionné et sa feuille Etudiants."
            )
        sheet = workbook[sheet_name]
        if (sheet.max_row or 0) > 100001 or (sheet.max_column or 0) > 100:
            raise StudentImportError(
                "La feuille dépasse 100 000 lignes ou 100 colonnes."
            )
        rows = iter(sheet.iter_rows())
        header = next(rows, ())
        if len(header) > 100:
            raise StudentImportError("La feuille dépasse 100 colonnes.")
        aliases = {
            "apogee": {"apogee", "numeroapogee", "napo", "napogee", "numapogee"},
            "nom": {"nom"},
            "prenom": {"prenom"},
            "filiere": {"filiere", "filieres"},
            "niveau": {"niveau", "niveaux"},
            "annee_universitaire": {"anneeuniversitaire"},
        }
        indices = {}
        for index, cell in enumerate(header):
            for field, labels in aliases.items():
                if header_key(cell.value) in labels:
                    if field in indices:
                        raise StudentImportError(
                            f"La colonne « {field} » figure plusieurs fois."
                        )
                    indices[field] = index
        if not {"apogee", "nom", "prenom"}.issubset(indices):
            raise StudentImportError(
                "La première ligne doit contenir les colonnes apogee, nom et prenom."
            )

        grouped = {}
        missing = duplicates = source_rows = 0
        for line, row in enumerate(rows, 2):
            if line > 100001 or len(row) > 100:
                raise StudentImportError(
                    "La feuille dépasse 100 000 lignes ou 100 colonnes."
                )

            def cell(field):
                index = indices.get(field)
                return row[index] if index is not None and index < len(row) else None

            if not any(
                c is not None and c.value is not None
                for c in (cell("apogee"), cell("nom"), cell("prenom"))
            ):
                continue
            source_rows += 1
            try:
                apogee = apogee_text(cell("apogee"))
                if not apogee:
                    missing += 1
                    continue
                values = {
                    field: cell_text(cell(field))
                    for field in aliases
                    if field != "apogee"
                }
                candidate = Etudiant(apogee=apogee, **values)
                candidate.full_clean(validate_unique=False, validate_constraints=False)
            except (StudentImportError, ValidationError) as exc:
                detail = (
                    "; ".join(exc.messages)
                    if isinstance(exc, ValidationError)
                    else str(exc)
                )
                raise StudentImportError(f"Ligne {line} : {detail}") from exc
            if apogee in grouped:
                existing = grouped[apogee]
                if not same_identity(Etudiant(**existing), values):
                    raise StudentImportError(
                        f"Ligne {line} : le même Apogée est associé à des noms différents. Corrigez le classeur avant l’import."
                    )
                for field in ("filiere", "niveau", "annee_universitaire"):
                    combined = dict.fromkeys(
                        (existing[field] + " / " + values[field]).split(" / ")
                    )
                    existing[field] = " / ".join(value for value in combined if value)
                try:
                    Etudiant(**existing).full_clean(
                        validate_unique=False, validate_constraints=False
                    )
                except ValidationError as exc:
                    raise StudentImportError(
                        f"Ligne {line} : les informations réunies dépassent la taille autorisée."
                    ) from exc
                duplicates += 1
            else:
                grouped[apogee] = dict(apogee=apogee, **values)
        return StudentImport(list(grouped.values()), missing, duplicates, source_rows)
    finally:
        workbook.close()

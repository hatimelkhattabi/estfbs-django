from pathlib import Path
import zipfile
from django.core.exceptions import ValidationError
from django.db import transaction
from openpyxl import load_workbook
from .models import Enseignant
from .teacher_forms import EnseignantForm, ppr_value


class TeacherImportError(ValueError):
    pass


def text(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def read_teachers(source):
    name = getattr(source, "name", str(source))
    if not str(name).lower().endswith(".xlsx"):
        raise TeacherImportError("Choisissez un fichier .xlsx.")
    if hasattr(source, "size") and source.size > 10 * 1024 * 1024:
        raise TeacherImportError("Le classeur doit peser au maximum 10 Mo.")
    try:
        with zipfile.ZipFile(source) as z:
            if sum(i.file_size for i in z.infolist()) > 40 * 1024 * 1024:
                raise TeacherImportError(
                    "Le classeur est trop volumineux une fois décompressé."
                )
        if hasattr(source, "seek"):
            source.seek(0)
        wb = load_workbook(source, read_only=True, data_only=True)
    except TeacherImportError:
        raise
    except Exception as exc:
        raise TeacherImportError(
            "Le fichier Excel est introuvable ou invalide."
        ) from exc
    try:
        if "Enseignants" not in wb.sheetnames:
            raise TeacherImportError("La feuille doit être nommée Enseignants.")
        sheet = wb["Enseignants"]
        rows = sheet.iter_rows(values_only=True)
        headers = [text(v).casefold() for v in next(rows, ())]
        expected = ["ppr", "cin", "nom", "prénom", "email", "département", "grade"]
        if headers[:7] != expected:
            raise TeacherImportError(
                "Utilisez les colonnes du modèle : PPR, CIN, Nom, Prénom, Email, Département, Grade."
            )
        result = []
        seen = set()
        for line, values in enumerate(rows, 2):
            if line > 10002:
                raise TeacherImportError("Le classeur est limité à 10 000 comptes.")
            row = [text(v) for v in values[:7]]
            row += [""] * (7 - len(row))
            if not any(row):
                continue
            try:
                ppr = ppr_value(row[0])
            except ValidationError as exc:
                raise TeacherImportError(f"Ligne {line} : PPR invalide.") from exc
            if ppr in seen:
                raise TeacherImportError(
                    f"Ligne {line} : le PPR {ppr} apparaît plusieurs fois. Aucun compte importé."
                )
            seen.add(ppr)
            result.append(
                {
                    "ppr": ppr,
                    "cin_initiale": row[1],
                    "nom": row[2],
                    "prenom": row[3],
                    "email": row[4],
                    "departement": row[5],
                    "grade": row[6],
                }
            )
        if not result:
            raise TeacherImportError(
                "Aucun compte renseigné dans la feuille Enseignants."
            )
        return result
    finally:
        wb.close()


@transaction.atomic
def import_teachers(rows, dry_run=False):
    created = updated = 0
    for line, row in enumerate(rows, 2):
        existing = (
            Enseignant.objects.select_related("utilisateur")
            .filter(ppr=row["ppr"])
            .first()
        )
        values = dict(row, actif=existing.actif if existing else True)
        if existing:
            values["cin_initiale"] = ""
        form = EnseignantForm(values, instance=existing)
        if not form.is_valid():
            errors = " ".join(str(e) for errors in form.errors.values() for e in errors)
            raise TeacherImportError(
                f"Ligne {line} : {errors} Aucune modification enregistrée."
            )
        if not dry_run:
            form.save()
        created += int(existing is None)
        updated += int(existing is not None)
    return {"created": created, "updated": updated}

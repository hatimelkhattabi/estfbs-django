from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from portal.models import Etudiant
from portal.student_import import StudentImportError, read_students, same_identity


class Command(BaseCommand):
    help = (
        "Importe les étudiants du classeur maître, uniquement sur leur numéro Apogée."
    )

    def add_arguments(self, parser):
        parser.add_argument("fichier", help="Chemin du classeur Excel .xlsx.")
        parser.add_argument(
            "--sheet",
            default="Etudiants",
            help="Feuille à lire (Etudiants par défaut).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Vérifier le classeur sans modifier la base.",
        )

    def handle(self, *args, **options):
        try:
            imported = read_students(options["fichier"], options["sheet"])
        except StudentImportError as exc:
            raise CommandError(str(exc)) from exc
        if not imported.students:
            raise CommandError(
                "Aucun numéro Apogée utilisable. Aucun étudiant importé."
            )

        created_count = existing_count = 0
        with transaction.atomic():
            existing = Etudiant.objects.in_bulk(
                [row["apogee"] for row in imported.students], field_name="apogee"
            )
            for values in imported.students:
                obj = existing.get(values["apogee"])
                if obj is not None and not same_identity(obj, values):
                    raise CommandError(
                        f"L’Apogée {values['apogee']} appartient déjà à une autre identité dans la base. Aucune modification enregistrée."
                    )
            for values in imported.students:
                apogee = values["apogee"]
                if options["dry_run"]:
                    created = apogee not in existing
                else:
                    defaults = {
                        key: value for key, value in values.items() if key != "apogee"
                    }
                    obj, created = Etudiant.objects.get_or_create(
                        apogee=apogee, defaults=defaults
                    )
                    if not same_identity(obj, values):
                        raise CommandError(
                            "Un Apogée a changé pendant l’import. Aucune modification enregistrée."
                        )
                created_count += int(created)
                existing_count += int(not created)

        prefix = "Simulation" if options["dry_run"] else "Import terminé"
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix} : {created_count} nouveau(x), {existing_count} déjà présent(s)."
            )
        )
        self.stdout.write(
            f"Apogées distincts dans le classeur : {len(imported.students)}"
        )
        self.stdout.write(f"Lignes sans Apogée ignorées : {imported.missing_apogee}")
        self.stdout.write(
            f"Doublons du même Apogée regroupés : {imported.duplicate_rows}"
        )
        if options["dry_run"]:
            self.stdout.write(
                "Aucune donnée modifiée. Relancez sans --dry-run pour importer."
            )
        else:
            self.stdout.write(
                "Les étudiants déjà présents conservent leurs informations et leur autorisation actuelle."
            )

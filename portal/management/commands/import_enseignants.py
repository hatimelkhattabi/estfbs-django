from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError
from portal.teacher_import import read_teachers, import_teachers, TeacherImportError


class Command(BaseCommand):
    help = "Importe les comptes enseignants par PPR. La CIN initialise seulement les nouveaux mots de passe."

    def add_arguments(self, parser):
        parser.add_argument("fichier")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        try:
            result = import_teachers(
                read_teachers(options["fichier"]), dry_run=options["dry_run"]
            )
        except (TeacherImportError, IntegrityError) as exc:
            raise CommandError(
                str(exc)
                if isinstance(exc, TeacherImportError)
                else "Conflit de PPR : aucun changement enregistré."
            ) from exc
        self.stdout.write(
            self.style.SUCCESS(
                ("Simulation" if options["dry_run"] else "Import terminé")
                + f" : {result['created']} création(s), {result['updated']} mise(s) à jour. Les mots de passe existants sont conservés."
            )
        )

"""Nettoyage planifié : seul un délai choisi explicitement rend une ligne éligible."""

from django.core.management.base import BaseCommand
from django.db import transaction
from portal.models import Publication


class Command(BaseCommand):
    help = "Liste les publications expirées ; --execute effectue leur suppression définitive."

    def add_arguments(self, parser):
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Supprime les publications arrivées à leur échéance.",
        )

    def handle(self, *args, **options):
        if not options["execute"]:
            for pk, title, due in (
                Publication.objects.expired()
                .order_by("pk")
                .values_list("pk", "titre", "date_suppression")
            ):
                self.stdout.write(f"{pk} — {title} — {due.isoformat()}")
            self.stdout.write(
                "Simulation uniquement. Ajoutez --execute pour supprimer les publications expirées."
            )
            return
        with transaction.atomic():
            ids = list(
                Publication.objects.expired()
                .order_by("pk")
                .select_for_update()
                .values_list("pk", flat=True)
            )
            if ids:
                Publication.objects.filter(pk__in=ids).delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"{len(ids)} publication(s) expirée(s) supprimée(s). Les fichiers envoyés sont conservés."
            )
        )

import json
from django.conf import settings
from django.core.management.base import BaseCommand
from portal.importing import import_rows


class Command(BaseCommand):
    help = "Charge le contenu présent dans l’archive d’origine, uniquement dans les tables vides."

    def handle(self, *args, **options):
        data = json.loads(
            (settings.BASE_DIR / "data/initial_data.json").read_text(encoding="utf-8")
        )
        result = import_rows(data, empty_only=True)
        for table, count in result.items():
            if count:
                self.stdout.write(f"{table} : {count} enregistrement(s).")
        self.stdout.write(
            self.style.SUCCESS(
                "Contenu initial prêt. Aucun compte ni mot de passe par défaut."
            )
        )

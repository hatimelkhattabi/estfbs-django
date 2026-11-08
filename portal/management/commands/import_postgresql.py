"""Charge un export contrôlé dans une nouvelle base PostgreSQL uniquement."""

import json
from pathlib import Path
from django.db import connection, transaction
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from portal.pg_transfer import counts, file_digest, validate_manifest


class Command(BaseCommand):
    help = "Importe un export_postgresql dans une base PostgreSQL vide après migrate."

    def add_arguments(self, parser):
        parser.add_argument(
            "dossier", type=Path, help="Dossier contenant manifest.json et data.json."
        )

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError("Cette commande exige DB_ENGINE=postgresql dans .env.")
        folder = options["dossier"].resolve()
        try:
            manifest = json.loads(
                (folder / "manifest.json").read_text(encoding="utf-8")
            )
        except (OSError, ValueError) as exc:
            raise CommandError("manifest.json introuvable ou invalide.") from exc
        expected = validate_manifest(manifest)
        fixture = folder / "data.json"
        if not fixture.is_file() or file_digest(fixture) != manifest.get("sha256"):
            raise CommandError(
                "L’export est incomplet ou modifié : empreinte data.json incorrecte."
            )
        with transaction.atomic():
            occupied = {name: n for name, n in counts().items() if n}
            if occupied:
                raise CommandError(
                    "La base cible contient déjà des données. Utilisez une nouvelle base PostgreSQL et lancez migrate, sans seed_site ni createsuperuser. Aucun remplacement effectué."
                )
            try:
                call_command(
                    "loaddata", str(fixture), database="default", stdout=self.stdout
                )
            except Exception as exc:
                raise CommandError(
                    f"Chargement interrompu : transaction annulée. {exc}"
                ) from exc
            actual = counts()
            if actual != expected:
                differences = [
                    name for name in expected if actual[name] != expected[name]
                ]
                raise CommandError(
                    "Comptages différents : "
                    + ", ".join(differences)
                    + ". Import annulé."
                )
        self.stdout.write(
            self.style.SUCCESS(
                "Import PostgreSQL terminé : tous les comptages correspondent."
            )
        )
        self.stdout.write(
            "Les identifiants et mots de passe Django ont été conservés. Reconnectez-vous au panneau."
        )
        for name, n in actual.items():
            if n:
                self.stdout.write(f"{name} : {n}")

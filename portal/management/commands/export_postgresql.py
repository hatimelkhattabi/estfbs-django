"""Exporte la base Django SQLite avant de changer le moteur dans .env."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from django.db import connection, transaction
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from portal.pg_transfer import EXCLUDED, counts, file_digest


class Command(BaseCommand):
    help = "Sauvegarde SQLite et export UTF-8 des données Django vers PostgreSQL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=Path,
            default=Path("sauvegardes"),
            help="Dossier parent des sauvegardes horodatées.",
        )

    def handle(self, *args, **options):
        if connection.vendor != "sqlite":
            raise CommandError(
                "Avant cet export, gardez DB_ENGINE=sqlite dans .env. La source est votre base Django actuelle."
            )
        if connection.in_atomic_block:
            raise CommandError("L’export doit être exécuté hors transaction active.")
        folder = options["output"].resolve() / datetime.now().strftime(
            "postgresql-%Y%m%d-%H%M%S-%f"
        )
        folder.mkdir(parents=True, exist_ok=False, mode=0o700)
        connection.ensure_connection()
        backup = folder / "db-avant-postgresql.sqlite3"
        with sqlite3.connect(backup) as destination:
            connection.connection.backup(destination)
        fixture = folder / "data.json"
        with transaction.atomic():
            before = counts()
            call_command(
                "dumpdata",
                database="default",
                exclude=EXCLUDED,
                natural_foreign=True,
                natural_primary=True,
                use_base_manager=True,
                indent=2,
                output=str(fixture),
                stdout=self.stdout,
            )
            if counts() != before:
                raise CommandError(
                    "Les données ont changé pendant l’export. Arrêtez le serveur puis réessayez."
                )
        manifest = {
            "format": "estfbs-postgresql-v1",
            "fixture": "data.json",
            "sha256": file_digest(fixture),
            "counts": before,
        }
        (folder / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self.stdout.write(
            self.style.SUCCESS("Export terminé. La base SQLite a été conservée.")
        )
        self.stdout.write("DOSSIER À IMPORTER : " + str(folder))
        for name, n in before.items():
            if n:
                self.stdout.write(f"{name} : {n}")

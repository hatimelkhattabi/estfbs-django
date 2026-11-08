import json
import os
import shutil
import sqlite3
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from portal.importing import TABLES, import_rows


class Command(BaseCommand):
    help = "Importe une source Laravel sans la modifier ; ajoute/met à jour par ID dans Django."

    def add_arguments(self, parser):
        g = parser.add_mutually_exclusive_group(required=True)
        g.add_argument("--sqlite", type=Path, help="Chemin du fichier SQLite Laravel.")
        g.add_argument(
            "--mysql",
            action="store_true",
            help="Lit les variables LARAVEL_DB_* dans .env.",
        )
        g.add_argument(
            "--json", type=Path, help="Objet JSON : table => liste de lignes."
        )
        parser.add_argument(
            "--files",
            type=Path,
            help="Dossier racine du projet Laravel pour copier les fichiers envoyés.",
        )
        parser.add_argument(
            "--admins",
            action="store_true",
            help="Importer aussi les comptes bcrypt Laravel (option explicite).",
        )
        parser.add_argument(
            "--timezone",
            default="UTC",
            help="Fuseau des dates sans indication dans Laravel ; UTC par défaut.",
        )

    def handle(self, *args, **options):
        try:
            ZoneInfo(options["timezone"])
        except ZoneInfoNotFoundError:
            raise CommandError("Fuseau source inconnu.")
        tables = list(TABLES) + (["administrateurs"] if options["admins"] else [])
        data = {}
        if options["sqlite"]:
            path = options["sqlite"].resolve()
            if not path.is_file():
                raise CommandError("Fichier SQLite introuvable.")
            con = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
            con.row_factory = sqlite3.Row
            try:
                existing = {
                    x[0]
                    for x in con.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                data = {
                    table: [
                        dict(x) for x in con.execute('SELECT * FROM "' + table + '"')
                    ]
                    for table in tables
                    if table in existing
                }
            finally:
                con.close()
        elif options["json"]:
            try:
                data = json.loads(options["json"].read_text(encoding="utf-8"))
            except (OSError, ValueError) as e:
                raise CommandError("Fichier JSON invalide.") from e
            if not isinstance(data, dict):
                raise CommandError("Le JSON doit contenir un objet table => lignes.")
        else:
            import pymysql

            source_name = os.getenv("LARAVEL_DB_NAME", "estfbs_laravel")
            target = settings.DATABASES["default"]
            if (
                target["ENGINE"].endswith("mysql")
                and source_name == target["NAME"]
                and os.getenv("LARAVEL_DB_HOST", "127.0.0.1") == target.get("HOST")
            ):
                raise CommandError(
                    "Utilisez une base cible Django différente de la source Laravel."
                )
            try:
                con = pymysql.connect(
                    host=os.getenv("LARAVEL_DB_HOST", "127.0.0.1"),
                    port=int(os.getenv("LARAVEL_DB_PORT", "3306")),
                    user=os.getenv("LARAVEL_DB_USER", "root"),
                    password=os.getenv("LARAVEL_DB_PASSWORD", ""),
                    database=source_name,
                    charset="utf8mb4",
                    cursorclass=pymysql.cursors.DictCursor,
                )
                with con.cursor() as cur:
                    cur.execute("SET TRANSACTION READ ONLY")
                    cur.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT")
                    cur.execute("SHOW TABLES")
                    existing = {next(iter(row.values())) for row in cur.fetchall()}
                    for table in tables:
                        if table in existing:
                            cur.execute("SELECT * FROM `" + table + "`")
                            data[table] = cur.fetchall()
                con.rollback()
                con.close()
            except pymysql.MySQLError as e:
                raise CommandError(
                    "Connexion à la source MySQL impossible. Vérifiez LARAVEL_DB_* dans .env et le service MySQL."
                ) from e
        result = import_rows(data, source_zone=options["timezone"])
        for table, count in result.items():
            if count:
                self.stdout.write(f"{table} : {count} importé(s).")
        if options["admins"]:
            for row in data.get("administrateurs", []):
                username = row.get("username", "")
                hashed = row.get("password_hash", "")
                if not username or not hashed.startswith(("$2y$", "$2b$", "$2a$")):
                    self.stdout.write(
                        "Compte non importé : utilisez createsuperuser ou changepassword."
                    )
                    continue
                if User.objects.filter(username=username).exists():
                    self.stdout.write(f"Compte existant conservé : {username}")
                    continue
                role = row.get("role", "")
                u = User.objects.create(
                    username=username,
                    password="laravel_bcrypt$" + hashed,
                    is_staff=True,
                    is_superuser=role.lower() in ["super admin", "superadmin"],
                    first_name=row.get("nom_complet", "")[:150],
                )
                if not u.is_superuser:
                    from django.contrib.auth.models import Permission

                    u.user_permissions.set(
                        Permission.objects.filter(content_type__app_label="portal")
                    )
        if options["files"]:
            root = options["files"].resolve()
            for folder, prefix in [
                (root / "storage/app/private", ""),
                (root / "public/uploads", "uploads"),
            ]:
                if not folder.exists():
                    continue
                for p in folder.rglob("*"):
                    if p.is_file() and not p.is_symlink() and p.name != ".gitignore":
                        dest = (
                            Path(settings.PRIVATE_MEDIA_ROOT)
                            / prefix
                            / p.relative_to(folder)
                        )
                        if not dest.exists():
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copyfile(p, dest)
        self.stdout.write(
            self.style.SUCCESS(
                "Import terminé. La source Laravel n’a pas été modifiée."
            )
        )

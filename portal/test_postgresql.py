"""Contrôles de transfert ; la logique est exercée sur SQLite, sans serveur PG."""

import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from django.contrib.auth import authenticate
from django.contrib.auth.models import User, Group, Permission
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.test import SimpleTestCase, TransactionTestCase, TestCase
from estfbs.database import database_config
from .models import Publication, UploadedDocument


class DatabaseConfigurationTests(SimpleTestCase):
    def test_engines_and_unknown_value(self):
        self.assertEqual(
            database_config("/tmp", {})["ENGINE"], "django.db.backends.sqlite3"
        )
        for alias in ["postgresql", "postgres", "pgsql"]:
            cfg = database_config(
                "/tmp",
                {
                    "DB_ENGINE": alias,
                    "DB_NAME": "estfbs_test",
                    "DB_USER": "application",
                    "DB_PASSWORD": "test",
                    "DB_SSLMODE": "require",
                },
            )
            self.assertEqual(cfg["ENGINE"], "django.db.backends.postgresql")
            self.assertEqual(cfg["PORT"], "5432")
            self.assertEqual(cfg["USER"], "application")
            self.assertEqual(cfg["OPTIONS"]["sslmode"], "require")
        self.assertEqual(
            database_config("/tmp", {"DB_ENGINE": "mysql"})["PORT"], "3306"
        )
        with self.assertRaises(ImproperlyConfigured):
            database_config("/tmp", {"DB_ENGINE": "typo"})


class DashboardCounterRegressionTests(TestCase):
    def test_visit_context_does_not_replace_administrative_counters(self):
        import re
        from .models import DemandeEtudiant, MessageContact, SiteVisit

        user = User.objects.create_superuser(
            "counter-test", "test@example.com", "Test-2026-Strong"
        )
        self.client.force_login(user)
        for i in range(12):
            DemandeEtudiant.objects.create(
                nom_prenom="Test",
                cne=str(i),
                cin="AB",
                filiere="GI",
                type_document="Attestation",
                email="t@example.com",
                statut="En attente" if i < 5 else ("Prête" if i < 8 else "En cours"),
            )
        for i in range(8):
            MessageContact.objects.create(
                nom_complet="Test",
                email="t@example.com",
                sujet="Message",
                message="Texte",
                statut="Nouveau" if i < 7 else "Traité",
            )
        for i in range(6):
            SiteVisit.objects.create(visitor_id="different-test")
        html = self.client.get("/admin/").content.decode()
        values = re.findall(r"<h3[^>]*>\s*(\d+)\s*</h3>", html)
        self.assertEqual(values, ["12", "5", "3", "7"])
        self.assertNotIn("no such element", html)


class PostgreSQLTransferTests(TransactionTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def export(self):
        call_command("export_postgresql", output=self.folder, stdout=io.StringIO())
        return next(self.folder.glob("postgresql-*"))

    def test_export_backup_and_roundtrip_preserves_accounts_relations_and_json(self):
        user = User.objects.create_superuser(
            "migration-test", "test@example.com", "Secret-Test-2026!"
        )
        group = Group.objects.create(name="Éditeurs")
        group.permissions.add(
            Permission.objects.get(
                codename="view_publication", content_type__app_label="portal"
            )
        )
        user.groups.add(group)
        p = Publication.objects.create(
            titre="إعلان — rentrée",
            resume="Résumé",
            publie=True,
            contenu_delta={"ops": [{"insert": "مرحبا\n"}]},
        )
        doc = UploadedDocument.objects.create(
            path="documents/existant.pdf",
            original_name="existant.pdf",
            mime="application/pdf",
            created_by=user,
        )
        folder = self.export()
        manifest = json.loads((folder / "manifest.json").read_text())
        self.assertEqual(manifest["counts"]["auth.user"], 1)
        self.assertTrue((folder / "db-avant-postgresql.sqlite3").is_file())
        rows = json.loads((folder / "data.json").read_text(encoding="utf-8"))
        self.assertNotIn("auth.permission", {row["model"] for row in rows})
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Publication.objects.get().titre, p.titre)
        with self.assertRaises(CommandError):
            call_command("import_postgresql", folder, stdout=io.StringIO())
        # Test portable loading/verification, not a substitute for a real PG server.
        with patch.object(connection, "vendor", "postgresql"):
            with self.assertRaises(CommandError):
                call_command("import_postgresql", folder, stdout=io.StringIO())
        User.objects.all().delete()
        Group.objects.all().delete()
        Publication.objects.all().delete()
        UploadedDocument.objects.all().delete()
        with patch.object(connection, "vendor", "postgresql"):
            call_command("import_postgresql", folder, stdout=io.StringIO())
        loaded = User.objects.get(username="migration-test")
        self.assertTrue(loaded.check_password("Secret-Test-2026!"))
        self.assertEqual(loaded.groups.get().name, "Éditeurs")
        self.assertTrue(loaded.has_perm("portal.view_publication"))
        self.assertEqual(
            UploadedDocument.objects.get(pk=doc.pk).created_by_id, loaded.pk
        )
        self.assertEqual(
            Publication.objects.get(pk=p.pk).contenu_delta, p.contenu_delta
        )

    def test_rejects_modified_or_invalid_export(self):
        folder = self.export()
        data = folder / "data.json"
        data.write_text("[]\n", encoding="utf-8")
        with patch.object(connection, "vendor", "postgresql"):
            with self.assertRaises(CommandError):
                call_command("import_postgresql", folder, stdout=io.StringIO())
        (folder / "manifest.json").write_text("{}", encoding="utf-8")
        with patch.object(connection, "vendor", "postgresql"):
            with self.assertRaises(CommandError):
                call_command("import_postgresql", folder, stdout=io.StringIO())

    def test_count_mismatch_rolls_back_import(self):
        user = User.objects.create_user("rollback-user", password="Secret-Test-2026!")
        folder = self.export()
        User.objects.all().delete()
        path = folder / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["counts"]["auth.user"] += 1
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with patch.object(connection, "vendor", "postgresql"):
            with self.assertRaises(CommandError):
                call_command("import_postgresql", folder, stdout=io.StringIO())
        self.assertFalse(User.objects.exists())

import io
from datetime import timedelta
from django.contrib.auth.models import User, Permission
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, Client, TransactionTestCase
from django.utils import timezone
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from .models import Publication, UploadedDocument


class AdminOptionsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_superuser(
            "options-test", "test@example.com", "Test-2026-Strong"
        )
        self.client.force_login(self.user)
        self.start = timezone.now().replace(second=0, microsecond=0) - timedelta(
            hours=1
        )

    def payload(self, **kw):
        data = dict(
            titre="Avis avec échéance",
            resume="Résumé",
            contenu="Contenu",
            type="Actualité",
            publie="1",
            date_publication=timezone.localtime(self.start).strftime("%Y-%m-%dT%H:%M"),
        )
        data.update(kw)
        return data

    def test_creator_is_separate_and_does_not_create_a_publication(self):
        r = self.client.get("/admin/createur-images")
        self.assertContains(r, 'data-mode="standalone"')
        self.assertContains(r, "data-cover-canvas")
        self.assertContains(r, "Télécharger en PNG")
        self.assertNotContains(r, "data-cover-apply")
        self.assertNotContains(r, 'name="titre"')
        self.assertFalse(Publication.objects.exists())
        r = self.client.get("/admin/publications/create")
        self.assertNotContains(r, "data-cover-canvas")
        self.assertContains(r, "/admin/createur-images")
        self.assertEqual(
            self.client.post("/admin/createur-images", {}).status_code, 405
        )
        for value in ["x", "²", "0", "99999999999999999999999999999"]:
            self.assertEqual(
                self.client.get(
                    "/admin/createur-images", {"publication": value}
                ).status_code,
                404,
            )
        self.client.logout()
        self.assertEqual(self.client.get("/admin/createur-images").status_code, 302)

    def test_creator_and_scheduling_permissions(self):
        user = User.objects.create_user(
            "editor", is_staff=True, password="Test-2026-Strong"
        )
        self.client.force_login(user)
        self.assertEqual(self.client.get("/admin/createur-images").status_code, 403)
        user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="portal",
                codename__in=[
                    "add_publication",
                    "change_publication",
                    "view_publication",
                ],
            )
        )
        self.assertContains(
            self.client.get("/admin/createur-images"), "data-cover-canvas"
        )
        self.assertNotContains(
            self.client.get("/admin/publications/create"),
            'name="suppression_apres_jours"',
        )
        r = self.client.post(
            "/admin/publications/create", self.payload(suppression_apres_jours="7")
        )
        self.assertEqual(r.status_code, 302)
        self.assertIsNone(Publication.objects.get().suppression_apres_jours)

    def test_schedule_update_cancel_and_display(self):
        r = self.client.post(
            "/admin/publications/create", self.payload(suppression_apres_jours="7")
        )
        self.assertEqual(r.status_code, 302)
        obj = Publication.objects.get()
        self.assertEqual(obj.date_suppression, self.start + timedelta(days=7))
        self.assertContains(
            self.client.get("/admin/publications"), "Suppression prévue"
        )
        self.assertContains(
            self.client.get(f"/admin/publications/{obj.pk}/edit"), 'value="7"'
        )
        # Un ancien client ne connaissant pas le champ ne retire pas le délai existant.
        self.client.post(f"/admin/publications/{obj.pk}/edit", self.payload())
        obj.refresh_from_db()
        self.assertEqual(obj.suppression_apres_jours, 7)
        self.client.post(
            f"/admin/publications/{obj.pk}/edit",
            self.payload(suppression_apres_jours=""),
        )
        obj.refresh_from_db()
        self.assertIsNone(obj.date_suppression)
        self.assertIsNone(obj.suppression_apres_jours)

    def test_invalid_or_already_elapsed_delay_is_rejected(self):
        for value in ["0", "-1", "3651", "1.5"]:
            self.assertEqual(
                self.client.post(
                    "/admin/publications/create",
                    self.payload(suppression_apres_jours=value),
                ).status_code,
                422,
            )
        self.assertEqual(
            self.client.post(
                "/admin/publications/create",
                self.payload(
                    suppression_apres_jours="1",
                    date_publication=timezone.localtime(
                        self.start - timedelta(days=3)
                    ).strftime("%Y-%m-%dT%H:%M"),
                ),
            ).status_code,
            422,
        )
        self.assertFalse(Publication.objects.exists())

    def test_expired_content_is_hidden_even_without_cleanup(self):
        expired = Publication.objects.create(
            titre="Publication expirée introuvable",
            resume="Texte",
            date_publication=self.start - timedelta(days=10),
            suppression_apres_jours=7,
            publie=True,
        )
        kept = Publication.objects.create(
            titre="Publication conservée",
            resume="Texte",
            date_publication=self.start - timedelta(days=100),
            publie=True,
        )
        future = Publication.objects.create(
            titre="Publication future",
            resume="Texte",
            date_publication=self.start + timedelta(days=10),
            suppression_apres_jours=7,
            publie=True,
        )
        self.assertEqual(
            future.date_suppression, future.date_publication + timedelta(days=7)
        )
        self.assertFalse(expired.visible)
        self.assertEqual(list(Publication.objects.published()), [kept])
        anon = Client()
        self.assertEqual(anon.get(f"/publications/{expired.pk}").status_code, 404)
        self.assertNotContains(anon.get("/actualites"), expired.titre)
        self.assertNotIn(
            expired.titre, str(anon.get("/backend/api/publications.php").json())
        )
        self.assertContains(
            self.client.get("/admin/publications?statut=expire"), expired.titre
        )
        self.assertContains(
            self.client.get(f"/publications/{expired.pk}?preview=1"), expired.titre
        )

    def test_cleanup_preview_execute_and_preserve_unselected_content_and_documents(
        self,
    ):
        due = Publication.objects.create(
            titre="À supprimer",
            resume="Texte",
            date_publication=self.start - timedelta(days=10),
            suppression_apres_jours=7,
        )
        kept = Publication.objects.create(
            titre="Sans délai",
            resume="Texte",
            date_publication=self.start - timedelta(days=100),
        )
        later = Publication.objects.create(
            titre="Plus tard",
            resume="Texte",
            date_publication=self.start,
            suppression_apres_jours=30,
        )
        doc = UploadedDocument.objects.create(
            path="documents/existant.pdf",
            original_name="existant.pdf",
            mime="application/pdf",
        )
        output = io.StringIO()
        call_command("purge_publications", stdout=output)
        self.assertIn(due.titre, output.getvalue())
        self.assertTrue(Publication.objects.filter(pk=due.pk).exists())
        call_command("purge_publications", execute=True, stdout=io.StringIO())
        self.assertFalse(Publication.objects.filter(pk=due.pk).exists())
        self.assertEqual(
            set(Publication.objects.values_list("pk", flat=True)), {kept.pk, later.pk}
        )
        self.assertTrue(UploadedDocument.objects.filter(pk=doc.pk).exists())
        call_command("purge_publications", execute=True, stdout=io.StringIO())
        self.assertEqual(Publication.objects.count(), 2)


class ExistingPublicationsMigrationTests(TransactionTestCase):
    def test_migration_preserves_existing_publications_without_scheduling_deletion(
        self,
    ):
        executor = MigrationExecutor(connection)
        executor.migrate([("portal", "0001_initial")])
        old = executor.loader.project_state(
            [("portal", "0001_initial")]
        ).apps.get_model("portal", "Publication")
        obj = old.objects.create(
            titre="Ancienne actualité", resume="Texte", publie=True
        )
        try:
            executor = MigrationExecutor(connection)
            executor.migrate([("portal", "0002_publication_scheduled_deletion")])
            current = Publication.objects.get(pk=obj.pk)
            self.assertEqual(current.titre, "Ancienne actualité")
            self.assertIsNone(current.suppression_apres_jours)
            self.assertIsNone(current.date_suppression)
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())

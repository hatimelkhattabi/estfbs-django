from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from django.contrib import admin
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from . import test_teacher_services as fixtures
from .models import DemandeImpression, DocumentImpression
from .test_teachers import pdf


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    ATTENDANCE_SOURCE_ROOT=None,
)
class PrintActionsTests(TestCase):
    setUp = fixtures.TeacherServicesTests.setUp
    tearDown = fixtures.TeacherServicesTests.tearDown
    batch = fixtures.TeacherServicesTests.batch
    post_batch = fixtures.TeacherServicesTests.post_batch

    def request(self):
        self.assertEqual(self.post_batch().status_code, 302)
        return DemandeImpression.objects.get()

    def url(self, item, action="modifier"):
        return f"/espace-enseignant/impressions/{item.reference}/{action}/"

    def edit_data(self, item):
        docs = list(item.documents.all())
        data = {
            "revision": item.modifie_le.isoformat(),
            "type_travail": item.type_travail,
            "remarque": "Consigne modifiée",
            "documents-TOTAL_FORMS": str(len(docs)),
            "documents-INITIAL_FORMS": str(len(docs)),
        }
        for i, doc in enumerate(docs):
            data[f"documents-{i}-document_id"] = str(doc.pk)
            for field in ["date_souhaitee", "exemplaires", "mode", "format_papier"]:
                data[f"documents-{i}-{field}"] = str(getattr(doc, field))
        return data

    def test_pending_requests_expose_edit_delete_and_existing_files_are_optional(self):
        item = self.request()
        for url in [
            "/espace-enseignant/mes-demandes/",
            f"/espace-enseignant/impressions/{item.reference}/",
        ]:
            response = self.client.get(url)
            self.assertContains(response, self.url(item))
            self.assertContains(response, self.url(item, "supprimer"))
        response = self.client.get(self.url(item))
        self.assertContains(response, "Remplacer le PDF (facultatif)")
        self.assertContains(response, "cours-0.pdf")
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_change_dates_copies_and_notes_without_reupload_or_identity_change(self):
        item = self.request()
        data = self.edit_data(item)
        data.update(
            enseignant=str(self.b.pk),
            statut="Terminée",
            reponse_administration="FORGED",
        )
        new_date = (timezone.localdate() + timedelta(days=15)).isoformat()
        data["documents-0-date_souhaitee"] = new_date
        data["documents-0-exemplaires"] = "73"
        ids = list(item.documents.values_list("pk", flat=True))
        paths = list(item.documents.values_list("document", flat=True))
        self.assertEqual(self.client.post(self.url(item), data).status_code, 302)
        item.refresh_from_db()
        self.assertEqual(
            (item.enseignant_id, item.statut, item.reponse_administration),
            (self.a.pk, "En attente", ""),
        )
        self.assertEqual(item.remarque, "Consigne modifiée")
        self.assertEqual(list(item.documents.values_list("pk", flat=True)), ids)
        self.assertEqual(list(item.documents.values_list("document", flat=True)), paths)
        self.assertEqual(item.documents.first().date_souhaitee.isoformat(), new_date)
        self.assertEqual(item.documents.first().exemplaires, 73)
        self.assertEqual(item.date_souhaitee, item.documents.last().date_souhaitee)

    def test_replace_remove_and_add_files_with_cleanup_only_after_commit(self):
        item = self.request()
        docs = list(item.documents.all())
        data = self.edit_data(item)
        data["documents-0-fichier"] = pdf("nouveau.pdf")
        data["documents-1-DELETE"] = "on"
        data.update(
            {
                "documents-TOTAL_FORMS": "3",
                "documents-2-fichier": pdf("annexe.pdf"),
                "documents-2-date_souhaitee": (
                    timezone.localdate() + timedelta(days=8)
                ).isoformat(),
                "documents-2-exemplaires": "12",
                "documents-2-mode": "recto",
                "documents-2-format_papier": "A4",
            }
        )
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.assertEqual(self.client.post(self.url(item), data).status_code, 302)
            self.assertTrue(
                all((Path(self.temp.name) / d.document).exists() for d in docs)
            )
        self.assertEqual(len(callbacks), 1)
        item.refresh_from_db()
        self.assertEqual(item.documents.count(), 2)
        self.assertEqual(item.documents.first().pk, docs[0].pk)
        self.assertFalse(DocumentImpression.objects.filter(pk=docs[1].pk).exists())
        self.assertEqual(item.nom_document, "nouveau.pdf")
        self.assertTrue(
            all(not (Path(self.temp.name) / d.document).exists() for d in docs)
        )
        self.assertTrue(
            all(
                (Path(self.temp.name) / d.document).exists()
                for d in item.documents.all()
            )
        )

    def test_delete_requires_confirmation_post_and_removes_only_own_files(self):
        item = self.request()
        url = self.url(item, "supprimer")
        self.assertContains(self.client.get(url), "Confirmer la suppression")
        self.assertEqual(self.client.post(url, {}).status_code, 200)
        self.assertTrue(DemandeImpression.objects.filter(pk=item.pk).exists())
        paths = list(item.documents.values_list("document", flat=True))
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url, {"revision": item.modifie_le.isoformat()})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(DemandeImpression.objects.filter(pk=item.pk).exists())
        self.assertFalse(DocumentImpression.objects.exists())
        self.assertTrue(all(not (Path(self.temp.name) / p).exists() for p in paths))

    def test_delete_preserves_file_still_referenced_by_another_request(self):
        item = self.request()
        shared = item.document
        other = DemandeImpression.objects.create(
            enseignant=self.b,
            document=shared,
            nom_document="shared.pdf",
            date_souhaitee=item.date_souhaitee,
            exemplaires=1,
        )
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                self.url(item, "supprimer"), {"revision": item.modifie_le.isoformat()}
            )
        self.assertTrue((Path(self.temp.name) / shared).exists())
        self.assertTrue(DemandeImpression.objects.filter(pk=other.pk).exists())

    def test_teacher_cannot_modify_or_delete_another_teachers_request(self):
        item = self.request()
        data = self.edit_data(item)
        self.client.force_login(self.b.utilisateur)
        for action in ["modifier", "supprimer"]:
            self.assertEqual(self.client.get(self.url(item, action)).status_code, 404)
            self.assertEqual(
                self.client.post(self.url(item, action), data).status_code, 404
            )
        self.assertEqual(DemandeImpression.objects.count(), 1)

    def test_seen_and_done_requests_are_locked_for_both_actions(self):
        item = self.request()
        for status in ["Vue", "Terminée"]:
            item.statut = status
            item.save()
            for action in ["modifier", "supprimer"]:
                self.assertEqual(
                    self.client.get(self.url(item, action)).status_code, 409
                )
                self.assertEqual(
                    self.client.post(
                        self.url(item, action), self.edit_data(item)
                    ).status_code,
                    409,
                )
            response = self.client.get("/espace-enseignant/mes-demandes/")
            self.assertNotContains(response, self.url(item))
            self.assertNotContains(response, self.url(item, "supprimer"))

    def test_stale_revision_rejects_edit_and_delete_without_writing_files(self):
        item = self.request()
        data = self.edit_data(item)
        data["documents-0-fichier"] = pdf("stale.pdf")
        item.remarque = "Nouvelle version"
        item.save()
        for action in ["modifier", "supprimer"]:
            self.assertEqual(
                self.client.post(self.url(item, action), data).status_code, 409
            )
        item.refresh_from_db()
        self.assertEqual(item.remarque, "Nouvelle version")
        self.assertEqual(len(list(Path(self.temp.name).rglob("*.pdf"))), 2)

    def test_status_is_checked_again_under_lock_before_saving(self):
        item = self.request()
        from . import teacher_print_actions as actions

        original = actions.owned_request

        def lookup(request, reference, lock=False):
            if lock:
                DemandeImpression.objects.filter(pk=item.pk).update(statut="Vue")
            return original(request, reference, lock)

        with patch.object(actions, "owned_request", side_effect=lookup):
            self.assertEqual(
                self.client.post(self.url(item), self.edit_data(item)).status_code, 409
            )
        item.refresh_from_db()
        self.assertNotEqual(item.remarque, "Consigne modifiée")

    def test_foreign_or_duplicate_document_ids_are_rejected(self):
        item = self.request()
        for value in ["999999999", str(item.documents.first().pk)]:
            data = self.edit_data(item)
            data["documents-1-document_id"] = value
            self.assertEqual(self.client.post(self.url(item), data).status_code, 200)
        self.assertEqual(item.documents.count(), 2)

    def test_total_size_includes_retained_pdfs_and_cannot_remove_every_document(self):
        item = self.request()
        with patch(
            "django.core.files.storage.FileSystemStorage.size",
            return_value=30 * 1024 * 1024,
        ):
            response = self.client.post(self.url(item), self.edit_data(item))
            self.assertContains(response, "dépassent 50 Mo")
        data = self.edit_data(item)
        for i in range(2):
            data[f"documents-{i}-DELETE"] = "on"
        self.assertEqual(self.client.post(self.url(item), data).status_code, 200)
        self.assertEqual(item.documents.count(), 2)

    def test_failed_edit_rolls_back_database_and_removes_only_new_upload(self):
        item = self.request()
        data = self.edit_data(item)
        data["documents-0-fichier"] = pdf("failed.pdf")
        paths = set(item.documents.values_list("document", flat=True))
        with patch.object(
            DocumentImpression, "save", side_effect=RuntimeError("write failed")
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url(item), data)
        item.refresh_from_db()
        self.assertEqual(set(item.documents.values_list("document", flat=True)), paths)
        self.assertEqual(
            set(
                str(p.relative_to(self.temp.name))
                for p in Path(self.temp.name).rglob("*.pdf")
            ),
            paths,
        )

    def test_legacy_request_without_children_can_be_edited_without_reupload(self):
        item = self.request()
        first = item.documents.first()
        item.documents.all().delete()
        data = {
            "revision": item.modifie_le.isoformat(),
            "type_travail": "autre",
            "documents-TOTAL_FORMS": "1",
            "documents-INITIAL_FORMS": "1",
            "documents-0-document_id": "legacy",
        }
        for field in ["date_souhaitee", "exemplaires", "mode", "format_papier"]:
            data["documents-0-" + field] = str(getattr(first, field))
        self.assertEqual(self.client.post(self.url(item), data).status_code, 302)
        self.assertEqual(item.documents.get().document, first.document)

    def test_edit_and_delete_require_csrf(self):
        item = self.request()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.a.utilisateur)
        for action in ["modifier", "supprimer"]:
            self.assertEqual(
                client.post(self.url(item, action), self.edit_data(item)).status_code,
                403,
            )

    def test_native_admin_status_save_does_not_overwrite_teacher_metadata(self):
        item = self.request()
        stale = DemandeImpression.objects.get(pk=item.pk)
        later = timezone.localdate() + timedelta(days=19)
        DemandeImpression.objects.filter(pk=item.pk).update(
            date_souhaitee=later, remarque="Teacher edit"
        )
        stale.statut = "Vue"
        admin.site._registry[DemandeImpression].save_model(None, stale, None, True)
        item.refresh_from_db()
        self.assertEqual(
            (item.date_souhaitee, item.remarque, item.statut),
            (later, "Teacher edit", "Vue"),
        )

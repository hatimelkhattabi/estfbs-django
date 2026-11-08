"""Independent exam settings, edit behavior and preservation of existing requests."""

from datetime import timedelta
from importlib import import_module
from types import SimpleNamespace
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from .models import DemandeImpression
from .printing_options import PRINT_OPTIONS
from . import test_teacher_services as fixtures


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    ATTENDANCE_SOURCE_ROOT=None,
)
class PerDocumentPrintingTests(TestCase):
    setUp = fixtures.TeacherServicesTests.setUp
    tearDown = fixtures.TeacherServicesTests.tearDown
    batch = fixtures.TeacherServicesTests.batch
    post_batch = fixtures.TeacherServicesTests.post_batch
    admin = fixtures.TeacherServicesTests.admin

    def data(self, *types):
        values = self.batch(len(types))
        values.pop("type_travail")
        for index, kind in enumerate(types):
            values[f"documents-{index}-type_travail"] = kind
        return values

    def add_supplies(self, data, index, **counts):
        for name, value in counts.items():
            data[f"documents-{index}-avec_{name}"] = "on"
            data[f"documents-{index}-{name}"] = str(value)

    def edit_data(self, item):
        docs = list(item.documents.all())
        data = {
            "revision": item.modifie_le.isoformat(),
            "remarque": "Demande corrigée",
            "documents-TOTAL_FORMS": str(len(docs)),
            "documents-INITIAL_FORMS": str(len(docs)),
        }
        for index, document in enumerate(docs):
            data[f"documents-{index}-document_id"] = str(document.pk)
            for key in PRINT_OPTIONS:
                data[f"documents-{index}-{key}"] = str(getattr(document, key))
            for name in ["feuilles_reponse", "papier_brouillon"]:
                if getattr(document, name):
                    data[f"documents-{index}-avec_{name}"] = "on"
        return data

    def test_mixed_request_keeps_each_type_deadline_and_exam_supplies(self):
        data = self.data("examen", "autre", "examen")
        self.add_supplies(data, 0, feuilles_reponse=20)
        self.add_supplies(data, 2, papier_brouillon=40)
        # Old top-level inputs cannot replace the new document-specific choices.
        data.update(type_travail="autre", feuilles_reponse="9999")
        self.assertEqual(self.post_batch(data).status_code, 302)
        item = DemandeImpression.objects.get()
        docs = list(item.documents.all())
        self.assertEqual([d.type_travail for d in docs], ["examen", "autre", "examen"])
        self.assertEqual([d.feuilles_reponse for d in docs], [20, 0, 0])
        self.assertEqual([d.papier_brouillon for d in docs], [0, 0, 40])
        self.assertEqual(len({d.date_souhaitee for d in docs}), 3)
        self.assertEqual(
            (item.type_travail, item.feuilles_reponse, item.papier_brouillon),
            ("mixte", 20, 40),
        )
        self.assertEqual(item.date_souhaitee, min(d.date_souhaitee for d in docs))
        for url in [
            f"/espace-enseignant/impressions/{item.reference}/",
            "/espace-enseignant/mes-demandes/",
        ]:
            self.assertContains(self.client.get(url), "Autre document")
        self.admin()
        response = self.client.get(f"/admin/impressions/{item.reference}/")
        for text in [
            "Examen et autres documents",
            "20 feuille(s) de réponse",
            "40 feuille(s) de brouillon",
            "cours-1.pdf",
        ]:
            self.assertContains(response, text)

    def test_form_has_document_specific_choices_and_supplies(self):
        response = self.client.get("/espace-enseignant/impression/")
        for name in [
            "type_travail",
            "date_souhaitee",
            "avec_feuilles_reponse",
            "avec_papier_brouillon",
        ]:
            self.assertContains(response, f'name="documents-0-{name}"')
            self.assertNotContains(response, f'name="{name}"')

    def test_checked_supplies_require_valid_quantities_for_that_document(self):
        for value in ["", "0", "-1", "10001", "abc"]:
            with self.subTest(value=value):
                data = self.data("autre", "examen")
                self.add_supplies(data, 1, feuilles_reponse=value)
                self.assertEqual(self.post_batch(data).status_code, 200)
                self.assertFalse(DemandeImpression.objects.exists())
        self.assertFalse(
            list(self.private.options["PRIVATE_MEDIA_ROOT"].rglob("*.pdf"))
        )

    def test_other_document_and_unchecked_exam_cannot_request_supplies(self):
        data = self.data("autre", "examen")
        self.add_supplies(data, 0, feuilles_reponse="abc", papier_brouillon=-5)
        data["documents-1-feuilles_reponse"] = "9999"
        self.assertEqual(self.post_batch(data).status_code, 302)
        item = DemandeImpression.objects.get()
        self.assertEqual((item.feuilles_reponse, item.papier_brouillon), (0, 0))
        self.assertTrue(
            all(
                d.feuilles_reponse == d.papier_brouillon == 0
                for d in item.documents.all()
            )
        )

    def test_missing_document_type_is_rejected_without_guessing_from_another_document(
        self,
    ):
        data = self.data("examen", "autre")
        del data["documents-1-type_travail"]
        data["type_travail"] = "examen"
        self.assertEqual(self.post_batch(data).status_code, 200)
        self.assertFalse(DemandeImpression.objects.exists())

    def test_old_global_form_allocates_supplies_once_to_the_earliest_document(self):
        data = self.batch(2, exam=True)
        data["documents-1-date_souhaitee"] = (
            timezone.localdate() + timedelta(days=2)
        ).isoformat()
        data.update(avec_feuilles_reponse="on", feuilles_reponse="52")
        self.assertEqual(self.post_batch(data).status_code, 302)
        docs = list(DemandeImpression.objects.get().documents.all())
        self.assertEqual([d.type_travail for d in docs], ["examen", "examen"])
        self.assertEqual([d.feuilles_reponse for d in docs], [0, 52])

    def test_edit_changes_one_exam_without_changing_another_document_or_its_pdf(self):
        data = self.data("examen", "examen")
        self.add_supplies(data, 0, feuilles_reponse=20)
        self.add_supplies(data, 1, papier_brouillon=30)
        self.assertEqual(self.post_batch(data).status_code, 302)
        item = DemandeImpression.objects.get()
        before = list(item.documents.values_list("pk", "document"))
        data = self.edit_data(item)
        data["documents-0-type_travail"] = "autre"
        data["documents-1-date_souhaitee"] = (
            timezone.localdate() + timedelta(days=20)
        ).isoformat()
        self.assertEqual(
            self.client.post(
                f"/espace-enseignant/impressions/{item.reference}/modifier/", data
            ).status_code,
            302,
        )
        item.refresh_from_db()
        docs = list(item.documents.all())
        self.assertEqual([(d.pk, d.document) for d in docs], before)
        self.assertEqual((docs[0].type_travail, docs[0].feuilles_reponse), ("autre", 0))
        self.assertEqual(
            (docs[1].type_travail, docs[1].papier_brouillon), ("examen", 30)
        )
        self.assertEqual(
            docs[1].date_souhaitee.isoformat(), data["documents-1-date_souhaitee"]
        )
        self.assertEqual(
            (item.type_travail, item.feuilles_reponse, item.papier_brouillon),
            ("mixte", 0, 30),
        )

    def test_removing_an_exam_recomputes_type_and_supplies(self):
        data = self.data("examen", "autre")
        self.add_supplies(data, 0, feuilles_reponse=45)
        self.assertEqual(self.post_batch(data).status_code, 302)
        item = DemandeImpression.objects.get()
        data = self.edit_data(item)
        data["documents-0-DELETE"] = "on"
        self.assertEqual(
            self.client.post(
                f"/espace-enseignant/impressions/{item.reference}/modifier/", data
            ).status_code,
            302,
        )
        item.refresh_from_db()
        self.assertEqual(item.documents.count(), 1)
        self.assertEqual(
            (item.type_travail, item.feuilles_reponse, item.papier_brouillon),
            ("autre", 0, 0),
        )

    def test_total_can_exceed_a_small_integer_without_exceeding_each_document_limit(
        self,
    ):
        data = self.data(*["examen"] * 4)
        for index in range(4):
            self.add_supplies(data, index, feuilles_reponse=10000)
        self.assertEqual(self.post_batch(data).status_code, 302)
        item = DemandeImpression.objects.get()
        self.assertEqual(item.feuilles_reponse, 40000)
        item.full_clean()


class PerDocumentMigrationTests(TransactionTestCase):
    def test_upgrade_preserves_old_types_files_and_supply_totals_without_duplication(
        self,
    ):
        before = [("portal", "0008_contact_apogee_only")]
        latest = [("portal", "0009_impression_options_par_document")]
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(latest))
        executor = MigrationExecutor(connection)
        executor.migrate(before)
        apps = executor.loader.project_state(before).apps
        user = apps.get_model("auth", "User").objects.create(
            username="previous-teacher"
        )
        teacher = apps.get_model("portal", "Enseignant").objects.create(
            utilisateur_id=user.pk, ppr="PREVIOUS", nom="Test"
        )
        due = timezone.localdate() + timedelta(days=10)
        values = dict(
            enseignant_id=teacher.pk,
            type_travail="examen",
            feuilles_reponse=25,
            papier_brouillon=50,
            document="impressions/previous.pdf",
            nom_document="Sujet.pdf",
            date_souhaitee=due,
            exemplaires=25,
        )
        Request = apps.get_model("portal", "DemandeImpression")
        request = Request.objects.create(**values)
        legacy = Request.objects.create(**values)
        Document = apps.get_model("portal", "DocumentImpression")
        late = Document.objects.create(
            demande_id=request.pk,
            document="impressions/late.pdf",
            nom_document="Annexe.pdf",
            date_souhaitee=due,
            exemplaires=25,
        )
        early = Document.objects.create(
            demande_id=request.pk,
            document="impressions/early.pdf",
            nom_document="Sujet.pdf",
            date_souhaitee=due - timedelta(days=2),
            exemplaires=25,
        )
        executor = MigrationExecutor(connection)
        executor.migrate(latest)
        apps = executor.loader.project_state(latest).apps
        Document = apps.get_model("portal", "DocumentImpression")
        docs = list(Document.objects.filter(demande_id=request.pk).order_by("pk"))
        self.assertEqual([d.type_travail for d in docs], ["examen", "examen"])
        self.assertEqual([d.feuilles_reponse for d in docs], [0, 25])
        self.assertEqual([d.papier_brouillon for d in docs], [0, 50])
        self.assertEqual([d.pk for d in docs], [late.pk, early.pk])
        self.assertEqual(
            [d.document for d in docs],
            ["impressions/late.pdf", "impressions/early.pdf"],
        )
        self.assertFalse(Document.objects.filter(demande_id=legacy.pk).exists())
        migrate = import_module(
            "portal.migrations.0009_impression_options_par_document"
        )
        migrate.preserve_document_options(apps, SimpleNamespace(connection=connection))
        self.assertEqual(
            sum(
                Document.objects.filter(demande_id=request.pk).values_list(
                    "feuilles_reponse", flat=True
                )
            ),
            25,
        )
        saved = apps.get_model("portal", "DemandeImpression").objects.get(pk=legacy.pk)
        self.assertEqual(
            (saved.type_travail, saved.feuilles_reponse, saved.document),
            ("examen", 25, "impressions/previous.pdf"),
        )

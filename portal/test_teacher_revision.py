"""Dates, print status permissions and simplified attendance selection."""

from datetime import timedelta
from pathlib import Path
from django.contrib.auth.models import User, Permission
from django.test import TestCase, TransactionTestCase, override_settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone
from .models import DemandeImpression, Etudiant
from .teacher_forms import AttendanceForm
from .test_teacher_services import TeacherServicesTests


# Reuse fixtures without inheriting the entire existing test class.
@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    ATTENDANCE_SOURCE_ROOT=None,
)
class TeacherRevisionTests(TestCase):
    setUp = TeacherServicesTests.setUp
    tearDown = TeacherServicesTests.tearDown
    batch = TeacherServicesTests.batch
    post_batch = TeacherServicesTests.post_batch
    admin = TeacherServicesTests.admin
    students = TeacherServicesTests.students

    def test_each_document_has_its_own_date_on_teacher_and_admin_pages(self):
        data = self.batch()
        early, late = timezone.localdate() + timedelta(
            days=3
        ), timezone.localdate() + timedelta(days=12)
        data["documents-0-date_souhaitee"] = late.isoformat()
        data["documents-1-date_souhaitee"] = early.isoformat()
        response = self.post_batch(data)
        self.assertEqual(response.status_code, 302)
        item = DemandeImpression.objects.get()
        self.assertEqual(
            list(item.documents.values_list("date_souhaitee", flat=True)), [late, early]
        )
        self.assertEqual(item.date_souhaitee, early)
        for url in [response.url, "/espace-enseignant/mes-demandes/"]:
            page = self.client.get(url)
            for date in [early, late]:
                self.assertContains(page, date.strftime("%d/%m/%Y"))
        self.admin()
        for url in [f"/admin/impressions/{item.reference}/", "/admin/impressions/"]:
            page = self.client.get(url)
            for date in [early, late]:
                self.assertContains(page, date.strftime("%d/%m/%Y"))

    def test_second_document_missing_or_past_date_saves_nothing(self):
        for value in ["", (timezone.localdate() - timedelta(days=1)).isoformat()]:
            with self.subTest(date=value):
                data = self.batch()
                data["documents-1-date_souhaitee"] = value
                self.assertEqual(self.post_batch(data).status_code, 200)
                self.assertFalse(DemandeImpression.objects.exists())
                self.assertEqual(list(Path(self.temp.name).rglob("*.pdf")), [])

    def test_legacy_batch_date_fills_only_omitted_individual_dates(self):
        data = self.batch()
        shared = timezone.localdate() + timedelta(days=7)
        first = data["documents-0-date_souhaitee"]
        data["date_souhaitee"] = shared.isoformat()
        data.pop("documents-1-date_souhaitee")
        self.assertEqual(self.post_batch(data).status_code, 302)
        docs = list(DemandeImpression.objects.get().documents.all())
        self.assertEqual(docs[0].date_souhaitee.isoformat(), first)
        self.assertEqual(docs[1].date_souhaitee, shared)

    def test_shared_table_and_its_old_partial_are_removed(self):
        other = DemandeImpression.objects.create(
            enseignant=self.b,
            document="impressions/PRIVATE.pdf",
            nom_document="PRIVATE.pdf",
            date_souhaitee=timezone.localdate(),
            exemplaires=4321,
        )
        for params in [{}, {"queue_only": "1", "impressions_page": "2"}]:
            response = self.client.get("/espace-enseignant/impression/", params)
            self.assertContains(response, "data-print-form")
            for value in [
                "data-print-queue",
                "Noms masqués",
                "PRIVATE.pdf",
                "4321",
                str(other.reference),
            ]:
                self.assertNotContains(response, value)
            self.assertContains(response, 'name="documents-0-date_souhaitee"')
            self.assertNotContains(response, 'name="date_souhaitee"')
            self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_admin_controls_exactly_three_statuses_and_reading_does_not_change_them(
        self,
    ):
        self.post_batch(self.batch(1))
        item = DemandeImpression.objects.get()
        self.admin()
        url = f"/admin/impressions/{item.reference}/"
        response = self.client.get(url)
        item.refresh_from_db()
        self.assertEqual(item.statut, "En attente")
        self.assertEqual(
            DemandeImpression.STATUTS,
            [(s, s) for s in ["En attente", "Vue", "Terminée"]],
        )
        for status in ["Vue", "Terminée", "En attente"]:
            self.assertContains(response, 'value="' + status + '"')
            self.assertEqual(
                self.client.post(
                    url, {"statut": status, "reponse_administration": "Suivi"}
                ).status_code,
                302,
            )
            item.refresh_from_db()
            self.assertEqual(item.statut, status)
        self.assertEqual(self.client.post(url, {"statut": "Acceptée"}).status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.statut, "En attente")

    def test_status_cannot_be_changed_by_teacher_or_view_only_staff(self):
        self.post_batch(self.batch(1))
        item = DemandeImpression.objects.get()
        url = f"/admin/impressions/{item.reference}/"
        self.assertIn(
            self.client.post(url, {"statut": "Terminée"}).status_code, [302, 403]
        )
        staff = User.objects.create_user("print-reader", is_staff=True)
        staff.user_permissions.add(
            Permission.objects.get(codename="view_demandeimpression")
        )
        self.client.force_login(staff)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url, {"statut": "Vue"}).status_code, 403)
        item.refresh_from_db()
        self.assertEqual(item.statut, "En attente")

    def test_attendance_has_only_three_year_choices_and_no_module_or_date(self):
        self.students()
        self.assertEqual(
            set(AttendanceForm().fields), {"filiere", "niveau", "annee_universitaire"}
        )
        self.assertEqual(AttendanceForm().fields["niveau"].label, "Année")
        self.assertEqual(
            list(AttendanceForm().fields["niveau"].choices),
            [
                ("", "Choisir…"),
                ("1", "1re année"),
                ("2", "2e année"),
                ("3", "3e année"),
            ],
        )
        response = self.client.get("/espace-enseignant/listes-presence/")
        for name in ["intitule", "date_seance"]:
            self.assertNotContains(response, 'name="' + name + '"')

    def test_attendance_normalizes_imported_years_without_matching_eleven(self):
        self.students()
        for i, year in enumerate(["1ère année", "Année 1", "première année", "1"], 20):
            Etudiant.objects.create(
                apogee=str(i),
                nom=f"Alias {i}",
                filiere="GI",
                niveau=year,
                annee_universitaire="2026-2027",
            )
        for selected in ["1", "1re année", "1ère année"]:
            response = self.client.get(
                "/espace-enseignant/listes-presence/",
                {
                    "filiere": "GI",
                    "niveau": selected,
                    "annee_universitaire": "2026-2027",
                },
            )
            self.assertContains(response, "6 étudiant(s)")
            self.assertNotContains(response, "Hors niveau")

    def test_removed_attendance_metadata_is_ignored_and_not_in_pdf_link(self):
        params = self.students()
        params.update(intitule="REMOVED_MODULE", date_seance="INVALID_DATE")
        response = self.client.get("/espace-enseignant/listes-presence/", params)
        self.assertContains(response, "2 étudiant(s)")
        self.assertNotContains(response, "REMOVED_MODULE")
        self.assertNotContains(response, "date_seance")


class TeacherRevisionMigrationTests(TransactionTestCase):
    def test_upgrade_backfills_dates_and_preserves_legacy_prints_and_refusal(self):
        latest = [("portal", "0009_impression_options_par_document")]
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(latest))
        executor = MigrationExecutor(connection)
        before = [("portal", "0005_espace_enseignant")]
        executor.migrate(before)
        old = executor.loader.project_state(before).apps
        user = old.get_model("auth", "User").objects.create(username="old-prof")
        teacher = old.get_model("portal", "Enseignant").objects.create(
            utilisateur_id=user.pk, ppr="LEGACY", nom="Test"
        )
        Request = old.get_model("portal", "DemandeImpression")
        due = timezone.localdate() + timedelta(days=9)
        ids = []
        for status in [
            "En attente",
            "Acceptée",
            "En cours",
            "Prête à récupérer",
            "Refusée",
        ]:
            item = Request.objects.create(
                enseignant_id=teacher.pk,
                statut=status,
                document=f"impressions/{len(ids)}.pdf",
                nom_document="old.pdf",
                date_souhaitee=due,
                exemplaires=35,
                reponse_administration="Réponse conservée",
            )
            ids.append(item.pk)
        middle = [("portal", "0006_services_enseignants")]
        executor = MigrationExecutor(connection)
        executor.migrate(middle)
        state = executor.loader.project_state(middle).apps
        import importlib

        backfill = importlib.import_module(
            "portal.migrations.0006_services_enseignants"
        ).preserve_existing_prints
        from types import SimpleNamespace

        backfill(state, SimpleNamespace(connection=connection))
        self.assertEqual(
            state.get_model("portal", "DocumentImpression").objects.count(), 5
        )
        extra = state.get_model("portal", "DocumentImpression").objects.create(
            demande_id=ids[0],
            document="impressions/extra.pdf",
            nom_document="extra.pdf",
            exemplaires=18,
        )
        executor = MigrationExecutor(connection)
        executor.migrate(latest)
        state = executor.loader.project_state(latest).apps
        requests = state.get_model("portal", "DemandeImpression").objects.order_by("pk")
        self.assertEqual(
            list(requests.values_list("statut", flat=True)),
            ["En attente", "Vue", "Vue", "Terminée", "Vue"],
        )
        docs = state.get_model("portal", "DocumentImpression").objects
        self.assertEqual(docs.count(), 6)
        self.assertEqual(set(docs.values_list("date_souhaitee", flat=True)), {due})
        self.assertEqual(docs.get(pk=extra.pk).exemplaires, 18)
        self.assertEqual(docs.get(pk=extra.pk).document, "impressions/extra.pdf")
        self.assertIn("Refusée", requests.last().reponse_administration)
        self.assertIn("Réponse conservée", requests.last().reponse_administration)
        self.assertEqual(requests.first().document, "impressions/0.pdf")

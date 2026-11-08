import io
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings

from .forms import ContactForm
from .models import Etudiant, MessageContact
from .student_import import (
    StudentImport,
    StudentImportError,
    apogee_text,
    read_students,
)


def excel_cell(value, data_type="s", number_format="General"):
    return SimpleNamespace(
        value=value, data_type=data_type, number_format=number_format
    )


def student_values(apogee="00123456", nom="TEST", prenom="Étudiant"):
    return dict(
        apogee=apogee,
        nom=nom,
        prenom=prenom,
        filiere="GI",
        niveau="2e année",
        annee_universitaire="2026-2027",
    )


class ExcelImportTests(TestCase):
    def test_cell_types_preserve_leading_zeros_and_reject_formulas(self):
        self.assertEqual(apogee_text(excel_cell("00123")), "00123")
        self.assertEqual(apogee_text(excel_cell(123, "n", "00000")), "00123")
        self.assertEqual(apogee_text(excel_cell(123.0, "n")), "123")
        for cell in [
            excel_cell("=123", "f"),
            excel_cell(12.5, "n"),
            excel_cell(True, "b"),
            excel_cell("12X"),
        ]:
            with self.subTest(value=cell.value), self.assertRaises(StudentImportError):
                apogee_text(cell)

    def parse_excel_rows(self, values, sheet="Etudiants", dimensions=True):
        cells = [[excel_cell(value) for value in row] for row in values]
        worksheet = SimpleNamespace(
            max_row=len(cells) if dimensions else None,
            max_column=len(cells[0]) if dimensions else None,
            iter_rows=lambda: iter(cells),
        )
        # Workbook __getitem__ uses its documented worksheet accessor.
        fake = type(
            "FakeWorkbook",
            (),
            {
                "sheetnames": ["Etudiants"],
                "close": lambda self: None,
                "__getitem__": lambda self, name: worksheet,
            },
        )()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "students.xlsx"
            path.write_bytes(b"fixture")
            with patch("portal.student_import.zipfile.ZipFile") as archive, patch(
                "openpyxl.load_workbook", return_value=fake
            ):
                archive.return_value.__enter__.return_value.infolist.return_value = []
                return read_students(path, sheet)

    def test_reader_deduplicates_apogee_only_and_skips_missing_ids(self):
        result = self.parse_excel_rows(
            [
                ["apogee", "nom", "prenom"],
                ["00123", "Même Nom", "Même Prénom"],
                ["00456", "Même Nom", "Même Prénom"],
                ["00123", "MÊME NOM", "MÊME PRÉNOM"],
                [None, "Même Nom", "Même Prénom"],
                [None, "Même Nom", "Même Prénom"],
            ]
        )
        self.assertEqual([s["apogee"] for s in result.students], ["00123", "00456"])
        self.assertEqual(
            (result.missing_apogee, result.duplicate_rows, result.source_rows),
            (2, 1, 5),
        )

    def test_reader_accepts_workbook_without_dimension_metadata(self):
        result = self.parse_excel_rows(
            [["apogee", "nom", "prenom"], ["00123456", "Test", "Étudiant"]],
            dimensions=False,
        )
        self.assertEqual(result.students[0]["apogee"], "00123456")

    def test_reader_rejects_conflicting_names_and_wrong_sheet(self):
        with self.assertRaisesMessage(StudentImportError, "noms différents"):
            self.parse_excel_rows(
                [["apogee", "nom", "prenom"], ["123", "A", "B"], ["123", "C", "D"]]
            )
        with self.assertRaisesMessage(StudentImportError, "introuvable"):
            self.parse_excel_rows([["apogee", "nom", "prenom"]], sheet="Doublons")

    def test_dry_run_and_repeated_import_do_not_duplicate_or_reactivate(self):
        planned = StudentImport([student_values(), student_values("00876543")], 3, 1, 6)
        with patch(
            "portal.management.commands.import_etudiants.read_students",
            return_value=planned,
        ):
            output = io.StringIO()
            call_command("import_etudiants", "test.xlsx", dry_run=True, stdout=output)
            self.assertEqual(Etudiant.objects.count(), 0)
            self.assertIn("3", output.getvalue())
            call_command("import_etudiants", "test.xlsx", stdout=io.StringIO())
            Etudiant.objects.filter(apogee="00123456").update(actif=False)
            call_command("import_etudiants", "test.xlsx", stdout=io.StringIO())
        self.assertEqual(Etudiant.objects.count(), 2)
        self.assertFalse(Etudiant.objects.get(apogee="00123456").actif)

    def test_conflict_with_existing_identity_leaves_everything_unchanged(self):
        original = Etudiant.objects.create(**student_values())
        planned = StudentImport(
            [student_values("00999999"), student_values(nom="Autre nom")], 0, 0, 2
        )
        with patch(
            "portal.management.commands.import_etudiants.read_students",
            return_value=planned,
        ):
            with self.assertRaisesMessage(CommandError, "autre identité"):
                call_command("import_etudiants", "test.xlsx", stdout=io.StringIO())
        self.assertEqual(Etudiant.objects.count(), 1)
        original.refresh_from_db()
        self.assertEqual(original.nom, "TEST")

    def test_database_enforces_unique_apogee_without_unique_names(self):
        Etudiant.objects.create(**student_values())
        Etudiant.objects.create(**student_values("00999999"))
        with transaction.atomic(), self.assertRaises(IntegrityError):
            Etudiant.objects.create(**student_values())


@override_settings(
    CONTACT_EMAIL="administration@example.com",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class StudentContactTests(TestCase):
    def setUp(self):
        cache.clear()
        self.student = Etudiant.objects.create(**student_values())
        self.payload = dict(
            nom="Nom libre saisi",
            email="etudiant@example.com",
            apogee=self.student.apogee,
            sujet="Question",
            message="Bonjour",
        )

    def post(self, **changes):
        return self.client.post(
            "/backend/api/submit_contact.php",
            json.dumps(self.payload | changes),
            content_type="application/json",
        )

    def test_known_apogee_creates_linked_message_and_email(self):
        response = self.post()
        self.assertEqual(response.status_code, 201)
        message = MessageContact.objects.get()
        self.assertEqual(message.etudiant_id, self.student.pk)
        self.assertEqual(message.apogee, "00123456")
        self.assertEqual(message.nom_complet, "Nom libre saisi")
        self.assertEqual(message.email, self.payload["email"])
        message.full_clean()
        self.assertIn("message a bien été envoyé", response.json()["message"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Apogée : 00123456", mail.outbox[0].body)
        self.assertIn("Email : etudiant@example.com", mail.outbox[0].body)
        self.assertNotIn("TEST", response.content.decode())

    def test_unknown_missing_and_malformed_apogee_save_nothing(self):
        for apogee in ["", "123456", "99999999", "not-a-number"]:
            with self.subTest(apogee=apogee):
                response = self.post(apogee=apogee)
                self.assertEqual(response.status_code, 422)
                self.assertIn("apogee", response.json()["errors"])
                self.assertNotIn("TEST", response.content.decode())
        self.assertEqual(MessageContact.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_inactive_student_is_rejected(self):
        self.student.actif = False
        self.student.save()
        self.assertEqual(self.post().status_code, 422)
        self.assertEqual(MessageContact.objects.count(), 0)

    def test_email_is_required_and_valid_but_does_not_replace_apogee(self):
        for value in ["", "invalid", "missing-domain@"]:
            with self.subTest(email=value):
                response = self.post(email=value)
                self.assertEqual(response.status_code, 422)
                self.assertIn("email", response.json()["errors"])
        self.assertEqual(self.post(apogee="", email="test@usms.ac.ma").status_code, 422)
        self.assertEqual(MessageContact.objects.count(), 0)

    def test_university_and_personal_emails_are_accepted(self):
        for email in ["etudiant@usms.ac.ma", "etudiant@example.com"]:
            self.assertEqual(self.post(email=email).status_code, 201)
            self.assertTrue(MessageContact.objects.filter(email=email).exists())

    def test_form_save_without_prior_validation_keeps_student_relation(self):
        values = {**self.payload, "nom_complet": self.payload["nom"]}
        form = ContactForm(values)
        result = form.save()
        self.assertEqual(result.etudiant_id, self.student.pk)

    def test_public_form_and_csrf_validation(self):
        client = Client(enforce_csrf_checks=True)
        response = client.get("/")
        self.assertContains(response, 'name="apogee"')
        self.assertContains(response, 'id="contact-email"')
        self.assertNotContains(response, self.student.apogee)
        self.assertEqual(
            client.post("/backend/api/submit_contact.php", self.payload).status_code,
            403,
        )
        response = client.post(
            "/backend/api/submit_contact.php",
            self.payload,
            HTTP_X_CSRF_TOKEN=client.cookies["csrftoken"].value,
        )
        self.assertEqual(response.status_code, 201)

    def test_deleting_registry_record_preserves_message_and_apogee_snapshot(self):
        self.assertEqual(self.post().status_code, 201)
        self.student.delete()
        message = MessageContact.objects.get()
        self.assertIsNone(message.etudiant_id)
        self.assertEqual(message.apogee, "00123456")


class StudentRegistryPanelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "student-manager", password="Long-test-password", is_staff=True
        )
        self.student = Etudiant.objects.create(**student_values())

    def test_registry_requires_authenticated_staff_and_model_permission(self):
        self.assertEqual(self.client.get("/admin/etudiants").status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/admin/etudiants").status_code, 403)
        self.user.user_permissions.add(Permission.objects.get(codename="view_etudiant"))
        self.assertContains(self.client.get("/admin/etudiants"), self.student.apogee)
        self.assertEqual(
            self.client.post(f"/admin/etudiants/{self.student.pk}/toggle").status_code,
            403,
        )

    def test_registry_creation_search_edit_and_toggle(self):
        self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/admin/etudiants/create").status_code, 200)
        self.assertEqual(
            self.client.post(
                "/admin/etudiants/create", student_values("00000123") | {"actif": "1"}
            ).status_code,
            302,
        )
        self.assertContains(
            self.client.get("/admin/etudiants", {"q": "00000123"}), "00000123"
        )
        self.assertEqual(
            self.client.get(f"/admin/etudiants/{self.student.pk}/edit").status_code, 200
        )
        self.assertEqual(
            self.client.post(f"/admin/etudiants/{self.student.pk}/toggle").status_code,
            302,
        )
        self.student.refresh_from_db()
        self.assertFalse(self.student.actif)
        self.assertEqual(
            self.client.get("/admin/etudiants/999999/toggle").status_code, 405
        )


class ExistingMessagesMigrationTests(TransactionTestCase):
    def test_existing_messages_survive_new_nullable_student_relation(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        old_target = [("portal", "0002_publication_scheduled_deletion")]
        executor.migrate(old_target)
        old = executor.loader.project_state(old_target).apps.get_model(
            "portal", "MessageContact"
        )
        message = old.objects.create(
            nom_complet="Ancien contact",
            email="old@example.com",
            sujet="Ancien message",
            message="Conserver",
        )
        try:
            MigrationExecutor(connection).migrate(latest)
            current = MessageContact.objects.get(pk=message.pk)
            self.assertEqual(current.message, "Conserver")
            self.assertEqual(current.apogee, "")
            self.assertIsNone(current.etudiant_id)
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())

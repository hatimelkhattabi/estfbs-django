import io
import tempfile
from pathlib import Path
from unittest.mock import patch
from datetime import timedelta
from django.contrib.auth.models import User, Permission
from django.core.cache import cache
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from .models import (
    DemandeImpression,
    DocumentImpression,
    DemandeDocumentAdministratif,
    Etudiant,
)
from .teacher_forms import PrintDocuments
from .test_teachers import teacher, pdf


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    ATTENDANCE_SOURCE_ROOT=None,
)
class TeacherServicesTests(TestCase):
    def setUp(self):
        cache.clear()
        self.a, self.b = teacher(), teacher("009999")
        self.temp = tempfile.TemporaryDirectory()
        self.private = override_settings(PRIVATE_MEDIA_ROOT=Path(self.temp.name))
        self.private.enable()
        self.client.force_login(self.a.utilisateur)

    def tearDown(self):
        self.private.disable()
        self.temp.cleanup()

    def admin(self):
        user = User.objects.create_superuser(
            "service-admin", "admin@example.com", "temporary-pass"
        )
        self.client.force_login(user)
        return user

    def batch(self, n=2, exam=False):
        values = {
            "type_travail": "examen" if exam else "autre",
            "intitule": "Algorithmique",
            "documents-TOTAL_FORMS": str(n),
            "documents-INITIAL_FORMS": "0",
            "documents-MIN_NUM_FORMS": "1",
            "documents-MAX_NUM_FORMS": "10",
        }
        for i in range(n):
            values.update(
                {
                    f"documents-{i}-date_souhaitee": (
                        timezone.localdate() + timedelta(days=5 + i)
                    ).isoformat(),
                    f"documents-{i}-fichier": pdf(f"cours-{i}.pdf"),
                    f"documents-{i}-exemplaires": str(20 + i),
                    f"documents-{i}-mode": "recto" if i else "recto-verso",
                    f"documents-{i}-format_papier": "A3" if i else "A4",
                    f"documents-{i}-couleur": "couleur" if i else "NB",
                }
            )
        return values

    def post_batch(self, values=None):
        return self.client.post(
            "/espace-enseignant/impression/",
            values if values is not None else self.batch(),
        )

    def administrative(self, **kwargs):
        return DemandeDocumentAdministratif.objects.create(
            enseignant=self.a, type_document="Attestation de travail", **kwargs
        )

    def students(self):
        for number, name, course, level, year, active in [
            (1, "Zaki", "GI", "1re année", "2026-2027", True),
            (2, "Amrani", "GI / Civil", "1re année / 2e année", "2026-2027", True),
            (3, "Hors filière", "GIM", "1re année", "2026-2027", True),
            (4, "Hors niveau", "GI", "11e année", "2026-2027", True),
            (5, "Hors année", "GI", "1re année", "2025-2026", True),
            (6, "Inactif", "GI", "1re année", "2026-2027", False),
        ]:
            Etudiant.objects.create(
                apogee=str(number).zfill(8),
                nom=name,
                prenom="Prénom",
                filiere=course,
                niveau=level,
                annee_universitaire=year,
                actif=active,
            )
        return {
            "filiere": "GI",
            "niveau": "1re année",
            "annee_universitaire": "2026-2027",
        }

    def test_dashboard_order_and_new_form_access(self):
        body = self.client.get("/espace-enseignant/").content.decode()
        titles = [
            "Demande d’impression",
            "Documents administratifs",
            "Listes de présence",
            "Demande de véhicule",
        ]
        positions = [body.index("<h2>" + name + "</h2>") for name in titles]
        self.assertEqual(positions, sorted(positions))
        for url in ["impression/", "documents-administratifs/", "listes-presence/"]:
            response = self.client.get("/espace-enseignant/" + url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Referrer-Policy"], "same-origin")
            self.assertEqual(response["Cache-Control"], "private, no-store")
        self.client.logout()
        for url in ["documents-administratifs/", "listes-presence/"]:
            self.assertEqual(
                self.client.get("/espace-enseignant/" + url).status_code, 302
            )

    def test_print_batch_stores_each_document_and_options(self):
        data = self.batch()
        data.update(
            {
                "enseignant": self.b.pk,
                "statut": "Prête à récupérer",
                "document": "stolen.pdf",
            }
        )
        response = self.post_batch(data)
        self.assertEqual(response.status_code, 302)
        item = DemandeImpression.objects.get()
        self.assertEqual(item.enseignant, self.a)
        self.assertEqual(item.statut, "En attente")
        docs = list(item.documents.all())
        self.assertEqual(len(docs), 2)
        self.assertEqual(
            (docs[0].exemplaires, docs[0].mode, docs[0].format_papier, docs[0].couleur),
            (20, "recto-verso", "A4", "NB"),
        )
        self.assertEqual(
            (docs[1].exemplaires, docs[1].mode, docs[1].format_papier, docs[1].couleur),
            (21, "recto", "A3", "NB"),
        )
        self.assertEqual(item.document, docs[0].document)
        self.assertTrue(
            all((Path(self.temp.name) / d.document).is_file() for d in docs)
        )
        self.assertContains(self.client.get(response.url), "cours-1.pdf")

    def test_printing_omits_metadata_and_forces_black_and_white(self):
        response = self.client.get("/espace-enseignant/impression/")
        for name in ["intitule", "filiere", "documents-0-couleur"]:
            self.assertNotContains(response, 'name="' + name + '"')
        data = self.batch()
        data["filiere"] = "Forged department"
        self.assertEqual(self.post_batch(data).status_code, 302)
        request = DemandeImpression.objects.get()
        self.assertEqual((request.intitule, request.filiere), ("", ""))
        self.assertEqual(request.couleur, "NB")
        self.assertEqual(
            list(request.documents.values_list("couleur", flat=True)), ["NB", "NB"]
        )

    def test_exam_supplies_have_explicit_quantities(self):
        data = self.batch(1, exam=True)
        data.update(
            {
                "avec_feuilles_reponse": "on",
                "feuilles_reponse": "20",
                "avec_papier_brouillon": "on",
                "papier_brouillon": "40",
            }
        )
        self.assertEqual(self.post_batch(data).status_code, 302)
        item = DemandeImpression.objects.get()
        self.assertEqual(
            (item.type_travail, item.feuilles_reponse, item.papier_brouillon),
            ("examen", 20, 40),
        )
        self.admin()
        response = self.client.get(f"/admin/impressions/{item.reference}/")
        self.assertContains(response, "20 feuille(s) de réponse")
        self.assertContains(response, "40 feuille(s) de brouillon")

    def test_non_exam_cannot_smuggle_supplies(self):
        data = self.batch(1)
        data.update(
            {
                "avec_feuilles_reponse": "on",
                "feuilles_reponse": "500",
                "avec_papier_brouillon": "on",
                "papier_brouillon": "500",
            }
        )
        self.assertEqual(self.post_batch(data).status_code, 302)
        item = DemandeImpression.objects.get()
        self.assertEqual((item.feuilles_reponse, item.papier_brouillon), (0, 0))

    def test_checked_supply_requires_quantity_and_saves_nothing_on_error(self):
        data = self.batch(1, exam=True)
        data["avec_feuilles_reponse"] = "on"
        response = self.post_batch(data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Indiquez le nombre total")
        self.assertFalse(DemandeImpression.objects.exists())
        self.assertEqual(list(Path(self.temp.name).rglob("*.pdf")), [])

    def test_invalid_second_document_is_atomic(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        data = self.batch()
        data["documents-1-fichier"] = SimpleUploadedFile("bad.pdf", b"bad")
        self.assertEqual(self.post_batch(data).status_code, 200)
        self.assertFalse(DemandeImpression.objects.exists())
        self.assertEqual(list(Path(self.temp.name).rglob("*.pdf")), [])

    def test_deleted_document_is_not_saved_or_required(self):
        data = self.batch()
        data.pop("documents-1-fichier")
        data["documents-1-DELETE"] = "on"
        self.assertEqual(self.post_batch(data).status_code, 302)
        self.assertEqual(DocumentImpression.objects.count(), 1)

    def test_maximum_document_count_and_total_size(self):
        self.assertEqual(self.post_batch(self.batch(11)).status_code, 200)
        self.assertFalse(DemandeImpression.objects.exists())
        data = self.batch(3)
        for index in range(3):
            data[f"documents-{index}-type_travail"] = "autre"
        files = {key: data.pop(key) for key in list(data) if key.endswith("-fichier")}
        for upload in files.values():
            upload.size = 20 * 1024 * 1024
        formset = PrintDocuments(data, files, prefix="documents")
        self.assertFalse(formset.is_valid())
        self.assertIn("50 Mo", str(formset.non_form_errors()))

    def test_files_are_removed_if_database_write_fails(self):
        with patch.object(
            DocumentImpression.objects,
            "bulk_create",
            side_effect=RuntimeError("write failed"),
        ):
            with self.assertRaises(RuntimeError):
                self.post_batch()
        self.assertFalse(DemandeImpression.objects.exists())
        self.assertEqual(list(Path(self.temp.name).rglob("*.pdf")), [])

    def test_each_print_file_requires_owner_or_authorized_admin(self):
        self.post_batch()
        item = DemandeImpression.objects.get()
        doc = item.documents.last()
        url = f"/espace-enseignant/impressions/{item.reference}/documents/{doc.pk}/"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.b.utilisateur)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.post_batch(self.batch(1))
        other = DemandeImpression.objects.exclude(pk=item.pk).get()
        self.assertEqual(
            self.client.get(
                f"/espace-enseignant/impressions/{other.reference}/documents/{doc.pk}/"
            ).status_code,
            404,
        )
        self.admin()
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_administrative_request_uses_session_identity(self):
        response = self.client.post(
            "/espace-enseignant/documents-administratifs/",
            {
                "type_document": "Attestation de travail",
                "motif": "Dossier administratif",
                "enseignant": self.b.pk,
                "statut": "Prête",
            },
        )
        self.assertEqual(response.status_code, 302)
        item = DemandeDocumentAdministratif.objects.get()
        self.assertEqual((item.enseignant, item.statut), (self.a, "En attente"))
        self.assertContains(self.client.get(response.url), "Attestation de travail")
        self.client.force_login(self.b.utilisateur)
        self.assertEqual(self.client.get(response.url).status_code, 404)
        self.assertNotContains(
            self.client.get("/espace-enseignant/mes-demandes/"),
            "Attestation de travail",
        )

    def test_other_administrative_document_needs_precision(self):
        response = self.client.post(
            "/espace-enseignant/documents-administratifs/",
            {"type_document": "Autre document"},
        )
        self.assertContains(response, "Indiquez le document souhaité")
        self.assertFalse(DemandeDocumentAdministratif.objects.exists())

    def test_admin_prepares_private_document_download_only_when_ready(self):
        item = self.administrative()
        self.admin()
        url = f"/admin/documents-enseignants/{item.reference}/"
        response = self.client.post(
            url,
            {
                "statut": "En cours",
                "fichier": pdf("attestation.pdf"),
                "reponse_administration": "En préparation",
            },
        )
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertTrue(item.document.startswith("administratifs/"))
        download = (
            f"/espace-enseignant/documents-administratifs/{item.reference}/document/"
        )
        self.assertEqual(self.client.get(download).status_code, 200)
        self.client.force_login(self.a.utilisateur)
        self.assertEqual(self.client.get(download).status_code, 404)
        self.admin_ready(item)
        response = self.client.get(download)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.client.force_login(self.b.utilisateur)
        self.assertEqual(self.client.get(download).status_code, 404)
        item.statut = "Refusée"
        item.save()
        self.client.force_login(self.a.utilisateur)
        self.assertEqual(self.client.get(download).status_code, 404)

    def admin_ready(self, item):
        item.statut = "Prête"
        item.save()

    def test_ready_without_pdf_has_pickup_instructions(self):
        item = self.administrative(
            statut="Prête", reponse_administration="Retrait au service RH"
        )
        response = self.client.get(
            f"/espace-enseignant/documents-administratifs/{item.reference}/"
        )
        self.assertContains(response, "retirer auprès")
        self.assertNotContains(response, "Télécharger mon document")

    def test_admin_permissions_and_invalid_administrative_upload(self):
        item = self.administrative()
        url = f"/admin/documents-enseignants/{item.reference}/"
        staff = User.objects.create_user("limited", password="pass", is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(url).status_code, 403)
        staff.user_permissions.add(
            Permission.objects.get(codename="view_demandedocumentadministratif")
        )
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url, {"statut": "Prête"}).status_code, 403)
        self.admin()
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.assertEqual(
            self.client.post(
                url,
                {"statut": "Prête", "fichier": SimpleUploadedFile("bad.pdf", b"bad")},
            ).status_code,
            200,
        )
        item.refresh_from_db()
        self.assertEqual(item.statut, "En attente")
        self.assertEqual(item.document, "")

    def test_attendance_exact_membership_active_sort_and_empty_selection(self):
        params = self.students()
        response = self.client.get("/espace-enseignant/listes-presence/", params)
        self.assertContains(response, "2 étudiant(s)")
        self.assertContains(response, "Amrani")
        self.assertContains(response, "Zaki")
        self.assertNotContains(response, "Hors filière")
        self.assertNotContains(response, "Hors niveau")
        self.assertNotContains(response, "Hors année")
        self.assertNotContains(response, "Inactif")
        self.assertLess(
            response.content.index(b"Amrani"), response.content.index(b"Zaki")
        )
        params["filiere"] = "GIM"
        params["niveau"] = "3"
        self.assertContains(
            self.client.get("/espace-enseignant/listes-presence/", params),
            "Aucun étudiant ne correspond",
        )

    def test_attendance_pdf_contains_only_selected_cohort_and_repeats_headers(self):
        params = self.students()
        params.update({"format": "pdf", "intitule": "Algorithmique & <analyse>"})
        for i in range(7, 72):
            Etudiant.objects.create(
                apogee=str(i).zfill(8),
                nom="Étudiant " + str(i),
                prenom="Test",
                filiere="GI",
                niveau="1re année",
                annee_universitaire="2026-2027",
            )
        response = self.client.get("/espace-enseignant/listes-presence/", params)
        self.assertEqual(response["Content-Type"], "application/pdf")
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(response.content))
        self.assertGreater(len(reader.pages), 1)
        alltext = "\n".join(page.extract_text() for page in reader.pages)
        self.assertIn("Amrani", alltext)
        self.assertNotIn("Hors filière", alltext)
        self.assertNotIn("Algorithmique & <analyse>", alltext)
        self.assertNotIn("Module / séance", alltext)
        self.assertNotIn("Date :", alltext)
        self.assertIn("1re année", alltext)
        for page in reader.pages:
            text = page.extract_text()
            self.assertIn("LISTE DE PRÉSENCE", text)
            self.assertIn("Signature", text)

    def test_attendance_invalid_filters_do_not_export_everyone(self):
        self.students()
        response = self.client.get(
            "/espace-enseignant/listes-presence/",
            {"format": "pdf", "filiere": "Unknown"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/html"))
        self.assertNotContains(response, "Zaki")

    def test_new_post_forms_still_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.a.utilisateur)
        self.assertEqual(
            client.post(
                "/espace-enseignant/documents-administratifs/",
                {"type_document": "Attestation de travail"},
            ).status_code,
            403,
        )
        self.assertEqual(
            client.post("/espace-enseignant/impression/", self.batch()).status_code, 403
        )

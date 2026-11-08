import io, json, tempfile, zipfile
from datetime import timedelta
from pathlib import Path
from xml.sax.saxutils import escape
from django.contrib.auth.models import User, Permission
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from .models import (
    Enseignant,
    DemandeVehicule,
    DemandeImpression,
    MessageAnonyme,
    SiteVisit,
)
from .teacher_forms import EnseignantForm
from .teacher_import import read_teachers, import_teachers, TeacherImportError


def teacher(ppr="001234", first=False):
    form = EnseignantForm(
        {
            "ppr": ppr,
            "nom": "Nom enseignant",
            "prenom": "Prénom",
            "email": "prof@usms.ac.ma",
            "grade": "PH",
            "departement": "Math - Informatiques",
            "actif": True,
            "cin_initiale": "AB123456",
        }
    )
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.changer_mot_de_passe = first
    obj.save()
    return obj


def pdf(name="cours.pdf"):
    return SimpleUploadedFile(
        name, b"%PDF-1.4\n% test-file\n%%EOF", content_type="application/pdf"
    )


def workbook(rows):
    # Minimal in-memory XLSX fixture for the importer, not a user workbook.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        )
        z.writestr(
            "_rels/.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        )
        z.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Enseignants" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        )
        data = []
        for index, row in enumerate(
            [["PPR", "CIN", "Nom", "Prénom", "Email", "Département", "Grade"]] + rows, 1
        ):
            cells = "".join(
                f'<c r="{chr(65+i)}{index}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
                for i, value in enumerate(row)
            )
            data.append(f'<row r="{index}">{cells}</row>')
        z.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
            + "".join(data)
            + "</sheetData></worksheet>",
        )
    return SimpleUploadedFile("enseignants.xlsx", buf.getvalue())


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    ATTENDANCE_SOURCE_ROOT=None,
)
class TeacherPortalTests(TestCase):
    def setUp(self):
        cache.clear()
        self.a = teacher()
        self.b = teacher("009999")
        self.tmp = tempfile.TemporaryDirectory()
        self.override = override_settings(PRIVATE_MEDIA_ROOT=Path(self.tmp.name))
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        self.tmp.cleanup()

    def login(self, who=None):
        self.client.force_login((who or self.a).utilisateur)

    def test_form_pages_preserve_same_origin_referrers(self):
        response = self.client.get("/espace-enseignant/connexion/")
        self.assertEqual(response["Referrer-Policy"], "same-origin")
        self.login()
        for url in [
            "/espace-enseignant/",
            "/espace-enseignant/mot-de-passe/",
            "/espace-enseignant/message-anonyme/",
            "/espace-enseignant/impression/",
            "/demande-vehicule",
        ]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Referrer-Policy"], "same-origin")
                self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_real_csrf_login_and_initial_password_change_http_and_https(self):
        host = "127.0.0.1:8001"
        for secure in (False, True):
            with self.subTest(secure=secure):
                profile = teacher("003502" if secure else "003501", first=True)
                client = Client(enforce_csrf_checks=True)
                origin = ("https" if secure else "http") + "://" + host
                headers = {"HTTP_HOST": host, "secure": secure}
                response = client.get("/espace-enseignant/connexion/", **headers)
                self.assertEqual(response["Referrer-Policy"], "same-origin")
                response = client.post(
                    "/espace-enseignant/connexion/",
                    {
                        "ppr": profile.ppr,
                        "password": "AB123456",
                        "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
                    },
                    HTTP_ORIGIN=origin,
                    **headers,
                )
                self.assertEqual(response.status_code, 302)
                self.assertIn("/mot-de-passe/", response.url)
                response = client.get("/espace-enseignant/mot-de-passe/", **headers)
                self.assertEqual(response["Referrer-Policy"], "same-origin")
                response = client.post(
                    "/espace-enseignant/mot-de-passe/",
                    {
                        "old_password": "AB123456",
                        "new_password1": "Mot-personnel-enseignant-2026!",
                        "new_password2": "Mot-personnel-enseignant-2026!",
                        "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
                    },
                    HTTP_ORIGIN=origin,
                    **headers,
                )
                self.assertEqual(response.status_code, 302)
                profile.refresh_from_db()
                self.assertFalse(profile.changer_mot_de_passe)
                self.assertContains(
                    client.get("/espace-enseignant/", **headers), "Message anonyme"
                )

    def test_csrf_still_rejects_null_foreign_origins_and_missing_tokens(self):
        client = Client(enforce_csrf_checks=True)
        client.get("/espace-enseignant/connexion/", HTTP_HOST="127.0.0.1:8001")
        token = client.cookies["csrftoken"].value
        for origin in ("null", "https://foreign.invalid"):
            with self.subTest(origin=origin):
                response = client.post(
                    "/espace-enseignant/connexion/",
                    {
                        "ppr": self.a.ppr,
                        "password": "AB123456",
                        "csrfmiddlewaretoken": token,
                    },
                    HTTP_HOST="127.0.0.1:8001",
                    HTTP_ORIGIN=origin,
                )
                self.assertEqual(response.status_code, 403)
        response = client.post(
            "/espace-enseignant/connexion/",
            {"ppr": self.a.ppr, "password": "AB123456"},
            HTTP_HOST="127.0.0.1:8001",
            HTTP_ORIGIN="http://127.0.0.1:8001",
        )
        self.assertEqual(response.status_code, 403)

    def test_https_csrf_accepts_same_origin_referer_without_origin_header(self):
        client = Client(enforce_csrf_checks=True)
        client.get(
            "/espace-enseignant/connexion/", HTTP_HOST="127.0.0.1:8001", secure=True
        )
        response = client.post(
            "/espace-enseignant/connexion/",
            {
                "ppr": self.a.ppr,
                "password": "AB123456",
                "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
            },
            HTTP_HOST="127.0.0.1:8001",
            HTTP_REFERER="https://127.0.0.1:8001/espace-enseignant/connexion/",
            secure=True,
        )
        self.assertEqual(response.status_code, 302)

    def payload(self):
        return {
            "date_visite": (timezone.localdate() + timedelta(days=5)).isoformat(),
            "destination": "Rabat",
            "effectif_etudiants": 20,
            "duree_visite": "Une journée",
        }

    def printing(self):
        return self.client.post(
            "/espace-enseignant/impression/",
            {
                "date_souhaitee": (
                    timezone.localdate() + timedelta(days=5)
                ).isoformat(),
                "exemplaires": 20,
                "mode": "recto-verso",
                "format_papier": "A4",
                "couleur": "NB",
                "fichier": pdf(),
                "statut": "Terminée",
                "enseignant": self.b.pk,
            },
        )

    def admin(self):
        obj = User.objects.create_superuser(
            "admin-q", "admin@example.com", "password-test"
        )
        self.client.force_login(obj)
        return obj

    def test_account_stores_hash_not_cin_and_has_no_staff_privileges(self):
        self.assertNotEqual(self.a.utilisateur.password, "AB123456")
        self.assertTrue(self.a.utilisateur.check_password("AB123456"))
        self.assertEqual(self.a.ppr, "001234")
        self.assertFalse(self.a.utilisateur.is_staff)
        self.assertFalse(self.a.utilisateur.is_superuser)
        self.a.utilisateur.full_clean()
        self.assertNotIn("cin", [field.name for field in Enseignant._meta.fields])

    def test_anonymous_users_cannot_open_services_or_submit_vehicles(self):
        for path in [
            "/espace-enseignant/",
            "/espace-enseignant/impression/",
            "/espace-enseignant/message-anonyme/",
            "/demande-vehicule",
            "/professeur/demande-vehicule",
            "/demande-vehicule/suivi",
        ]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302)
            self.assertIn("/espace-enseignant/connexion/", response.url)
        for path in [
            "/demande-vehicule",
            "/professeur/demande-vehicule",
            "/demande-vehicule/ordre-mission-pdf",
        ]:
            response = self.client.post(
                path, json.dumps(self.payload()), content_type="application/json"
            )
            self.assertEqual(response.status_code, 401)
        self.assertFalse(DemandeVehicule.objects.exists())

    def test_first_login_forces_password_change_and_preserves_ppr_zeros(self):
        self.a.changer_mot_de_passe = True
        self.a.save()
        response = self.client.post(
            "/espace-enseignant/connexion/", {"ppr": "001234", "password": "ab123456"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/mot-de-passe/", response.url)
        for path in [
            "/espace-enseignant/",
            "/espace-enseignant/impression/",
            "/demande-vehicule",
        ]:
            self.assertIn("/mot-de-passe/", self.client.get(path).url)
        response = self.client.post(
            "/espace-enseignant/mot-de-passe/",
            {
                "old_password": "ab123456",
                "new_password1": "UnNouveauSoleil!2026",
                "new_password2": "UnNouveauSoleil!2026",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.a.refresh_from_db()
        self.assertFalse(self.a.changer_mot_de_passe)
        self.assertEqual(self.client.get("/espace-enseignant/").status_code, 200)
        self.client.logout()
        self.assertEqual(
            self.client.post(
                "/espace-enseignant/connexion/",
                {"ppr": self.a.ppr, "password": "AB123456"},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                "/espace-enseignant/connexion/",
                {"ppr": self.a.ppr, "password": "UnNouveauSoleil!2026"},
            ).status_code,
            302,
        )

    def test_external_next_is_not_used(self):
        response = self.client.post(
            "/espace-enseignant/connexion/",
            {"ppr": self.a.ppr, "password": "AB123456", "next": "https://evil.example"},
        )
        self.assertEqual(response.url, "/espace-enseignant/")

    def test_reusing_initial_password_is_rejected(self):
        self.a.changer_mot_de_passe = True
        self.a.save()
        self.login()
        response = self.client.post(
            "/espace-enseignant/mot-de-passe/",
            {
                "old_password": "AB123456",
                "new_password1": "AB123456",
                "new_password2": "AB123456",
            },
        )
        self.assertContains(response, "différent du mot de passe actuel")
        self.a.refresh_from_db()
        self.assertTrue(self.a.changer_mot_de_passe)

    def test_inactive_profile_blocks_existing_session(self):
        self.login()
        self.a.actif = False
        self.a.save()
        self.assertEqual(self.client.get("/espace-enseignant/").status_code, 403)

    def test_home_has_three_services_and_private_pages_are_not_visitor_tracked(self):
        self.login()
        response = self.client.get("/espace-enseignant/")
        for text in [
            "Message anonyme",
            "Demande de véhicule",
            "Demande d’impression",
            "Mes demandes",
        ]:
            self.assertContains(response, text)
        self.client.get("/espace-enseignant/message-anonyme/")
        self.assertEqual(SiteVisit.objects.count(), 0)
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_vehicle_submission_uses_authenticated_identity(self):
        self.login()
        response = self.client.post(
            "/demande-vehicule",
            json.dumps(
                self.payload()
                | {
                    "nom_professeur": "Faux nom",
                    "email_professeur": "attacker@example.com",
                    "enseignant": self.b.pk,
                    "statut": "Validée",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        obj = DemandeVehicule.objects.get()
        self.assertEqual(obj.enseignant, self.a)
        self.assertEqual(obj.nom_professeur, self.a.nom_complet)
        self.assertEqual(obj.email_professeur, self.a.email)
        self.assertFalse(obj.ordre_mission_disponible)

    def test_vehicle_urls_and_generic_tracking_do_not_leak_other_owners(self):
        obj = DemandeVehicule.objects.create(
            enseignant=self.b,
            nom_professeur="Autre professeur",
            date_visite=timezone.localdate(),
            effectif_etudiants=20,
            destination="Adresse privée",
            duree_visite="1 jour",
            statut="Validée",
        )
        self.login()
        base = "/demande-vehicule/" + obj.code_suivi
        for suffix in ["", "/pdf", "/ordre-mission-pdf"]:
            self.assertEqual(self.client.get(base + suffix).status_code, 404)
        for path in [
            "/suivi.php",
            "/backend/api/check_status.php",
            "/demande-vehicule/suivi",
        ]:
            response = self.client.get(path, {"code": obj.code_suivi})
            self.assertNotContains(response, "Adresse privée")
            if path.endswith("check_status.php"):
                self.assertFalse(response.json()["success"])
        self.assertNotContains(
            self.client.get("/espace-enseignant/mes-demandes/"), "Adresse privée"
        )

    def test_legacy_vehicle_stays_admin_only(self):
        obj = DemandeVehicule.objects.create(
            nom_professeur="Ancien professeur",
            date_visite=timezone.localdate(),
            effectif_etudiants=20,
            destination="Ancien dossier",
            duree_visite="1 jour",
        )
        self.login()
        self.assertEqual(
            self.client.get("/demande-vehicule/" + obj.code_suivi).status_code, 404
        )
        self.admin()
        self.assertEqual(
            self.client.get("/demande-vehicule/" + obj.code_suivi).status_code, 200
        )

    def test_printing_records_exact_options_and_private_file(self):
        self.login()
        response = self.printing()
        self.assertEqual(response.status_code, 302)
        obj = DemandeImpression.objects.get()
        self.assertEqual(obj.enseignant, self.a)
        self.assertEqual(
            (obj.exemplaires, obj.format_papier, obj.mode, obj.couleur, obj.statut),
            (20, "A4", "recto-verso", "NB", "En attente"),
        )
        self.assertTrue((Path(self.tmp.name) / obj.document).is_file())
        self.assertContains(self.client.get(response.url), "20")
        file_url = f"/espace-enseignant/impressions/{obj.reference}/document/"
        response = self.client.get(file_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.login(self.b)
        self.assertEqual(self.client.get(file_url).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(file_url).status_code, 302)

    def test_invalid_print_file_and_date_are_rejected(self):
        self.login()
        data = {
            "date_souhaitee": (timezone.localdate() - timedelta(days=1)).isoformat(),
            "exemplaires": 0,
            "mode": "recto-verso",
            "format_papier": "A4",
            "couleur": "NB",
            "fichier": SimpleUploadedFile("bad.pdf", b"<script>bad</script>"),
        }
        self.assertEqual(
            self.client.post("/espace-enseignant/impression/", data).status_code, 200
        )
        self.assertFalse(DemandeImpression.objects.exists())
        self.assertEqual(list(Path(self.tmp.name).rglob("*.pdf")), [])

    def test_admin_can_process_print_and_owner_sees_response(self):
        self.login()
        self.printing()
        obj = DemandeImpression.objects.get()
        self.admin()
        url = f"/admin/impressions/{obj.reference}/"
        response = self.client.post(
            url,
            {
                "statut": "Terminée",
                "reponse_administration": "À retirer au bureau informatique.",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.login()
        response = self.client.get(f"/espace-enseignant/impressions/{obj.reference}/")
        self.assertContains(response, "Terminée")
        self.assertContains(response, "À retirer au bureau informatique.")

    def test_anonymous_message_has_no_link_to_sender(self):
        self.login()
        response = self.client.post(
            "/espace-enseignant/message-anonyme/",
            {
                "sujet": "Proposition",
                "message": "Améliorer la disponibilité des salles.",
                "enseignant": self.a.pk,
                "ppr": self.a.ppr,
                "email": self.a.email,
            },
        )
        self.assertEqual(response.status_code, 302)
        obj = MessageAnonyme.objects.get()
        self.assertEqual(
            {f.name for f in obj._meta.fields},
            {"id", "sujet", "message", "statut", "date_envoi"},
        )
        self.assertNotIn(self.a.ppr, str(obj.__dict__))
        self.assertEqual(SiteVisit.objects.count(), 0)

    def test_teacher_cannot_read_anonymous_inbox_or_manage_accounts(self):
        self.login()
        for path in [
            "/admin/messages-anonymes/",
            "/admin/comptes-enseignants/",
            "/admin/impressions/",
        ]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302)
            self.assertIn("/admin/login/", response.url)

    def test_admin_messages_are_escaped_and_moderated(self):
        obj = MessageAnonyme.objects.create(
            sujet="Proposition", message="<script>alert(12345)</script>"
        )
        self.admin()
        url = f"/admin/messages-anonymes/{obj.pk}/"
        response = self.client.get(url)
        self.assertContains(response, "&lt;script&gt;alert(12345)")
        self.assertNotContains(response, "<script>alert(12345)</script>")
        self.assertEqual(self.client.post(url, {"statut": "Traité"}).status_code, 302)
        obj.refresh_from_db()
        self.assertEqual(obj.statut, "Traité")

    def test_admin_can_create_and_reset_accounts(self):
        self.admin()
        values = {
            "ppr": "000777",
            "nom": "Test accès",
            "prenom": "Professeur",
            "cin_initiale": "CD123456",
            "actif": "on",
        }
        response = self.client.post("/admin/comptes-enseignants/ajouter/", values)
        self.assertEqual(response.status_code, 302)
        obj = Enseignant.objects.get(ppr="000777")
        self.assertTrue(obj.utilisateur.check_password("CD123456"))
        self.assertTrue(obj.changer_mot_de_passe)
        obj.changer_mot_de_passe = False
        obj.save()
        values.update(cin_initiale="EF123456")
        self.assertEqual(
            self.client.post(
                f"/admin/comptes-enseignants/{obj.pk}/", values
            ).status_code,
            302,
        )
        obj.refresh_from_db()
        self.assertTrue(obj.changer_mot_de_passe)
        self.assertTrue(obj.utilisateur.check_password("EF123456"))

    def test_view_permission_does_not_allow_print_status_changes(self):
        self.login()
        self.printing()
        obj = DemandeImpression.objects.get()
        staff = User.objects.create_user("viewer", password="pass", is_staff=True)
        staff.user_permissions.add(
            Permission.objects.get(codename="view_demandeimpression")
        )
        self.client.force_login(staff)
        url = f"/admin/impressions/{obj.reference}/"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url, {"statut": "Acceptée"}).status_code, 403)
        obj.refresh_from_db()
        self.assertEqual(obj.statut, "En attente")

    def test_logout_and_submissions_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.a.utilisateur)
        self.assertEqual(client.get("/espace-enseignant/deconnexion/").status_code, 405)
        for path in [
            "/espace-enseignant/deconnexion/",
            "/espace-enseignant/message-anonyme/",
            "/espace-enseignant/impression/",
            "/demande-vehicule",
        ]:
            self.assertEqual(client.post(path, {}).status_code, 403)


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    ATTENDANCE_SOURCE_ROOT=None,
)
class TeacherImportTests(TestCase):
    def test_import_duplicate_names_but_unique_ppr_and_leading_zero(self):
        rows = read_teachers(
            workbook(
                [
                    ["000001", "AB123456", "Même nom", "Prénom", "", "", "PES"],
                    ["000002", "CD123456", "Même nom", "Prénom", "", "", "PH"],
                ]
            )
        )
        result = import_teachers(rows)
        self.assertEqual(result["created"], 2)
        self.assertEqual(Enseignant.objects.count(), 2)
        self.assertTrue(
            Enseignant.objects.get(ppr="000001").utilisateur.check_password("AB123456")
        )

    def test_reimport_preserves_password_and_disabled_status(self):
        obj = teacher()
        obj.changer_mot_de_passe = False
        obj.actif = False
        obj.save()
        obj.utilisateur.set_password("Mot-de-passe-personnel!2026")
        obj.utilisateur.save()
        row = {
            "ppr": obj.ppr,
            "cin_initiale": "NOUVELLE123",
            "nom": "Nom corrigé",
            "prenom": "Prénom",
            "email": "",
            "departement": "",
            "grade": "PES",
        }
        result = import_teachers([row])
        self.assertEqual(result["updated"], 1)
        obj.refresh_from_db()
        self.assertFalse(obj.actif)
        self.assertFalse(obj.changer_mot_de_passe)
        self.assertTrue(obj.utilisateur.check_password("Mot-de-passe-personnel!2026"))

    def test_dry_run_does_not_create_accounts(self):
        rows = read_teachers(
            workbook([["000001", "AB123456", "Nom", "Prénom", "", "", "PES"]])
        )
        self.assertEqual(import_teachers(rows, dry_run=True)["created"], 1)
        self.assertFalse(Enseignant.objects.exists())
        self.assertFalse(User.objects.exists())

    def test_duplicate_ppr_rejects_whole_file(self):
        with self.assertRaises(TeacherImportError):
            read_teachers(
                workbook(
                    [
                        ["000001", "AB123456", "Nom", "", "", "", ""],
                        ["000001", "AB123456", "Autre", "", "", "", ""],
                    ]
                )
            )
        self.assertFalse(User.objects.exists())

    def test_bad_second_row_rolls_back_first_account(self):
        rows = read_teachers(
            workbook(
                [
                    ["000001", "AB123456", "Nom", "", "", "", ""],
                    ["000002", "", "Nom", "", "", "", ""],
                ]
            )
        )
        with self.assertRaises(TeacherImportError):
            import_teachers(rows)
        self.assertFalse(User.objects.exists())
        self.assertFalse(Enseignant.objects.exists())


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    ATTENDANCE_SOURCE_ROOT=None,
)
class TeacherAdditionalValidationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.profile = teacher()
        self.client.force_login(self.profile.utilisateur)

    def test_fake_pdf_rejected_with_other_fields_valid(self):
        data = {
            "date_souhaitee": timezone.localdate().isoformat(),
            "exemplaires": 20,
            "mode": "recto-verso",
            "format_papier": "A4",
            "couleur": "NB",
            "fichier": SimpleUploadedFile("faux.pdf", b"<html>not pdf</html>"),
        }
        response = self.client.post("/espace-enseignant/impression/", data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(DemandeImpression.objects.exists())

    def test_initial_cin_cannot_be_reused_with_lowercase(self):
        self.profile.changer_mot_de_passe = True
        self.profile.save()
        response = self.client.post(
            "/espace-enseignant/mot-de-passe/",
            {
                "old_password": "AB123456",
                "new_password1": "ab123456",
                "new_password2": "ab123456",
            },
        )
        self.assertContains(response, "différent du mot de passe actuel")
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.changer_mot_de_passe)

    def test_excel_template_is_admin_only_and_preserves_identifier_format(self):
        from openpyxl import load_workbook

        url = "/admin/comptes-enseignants/modele/"
        self.assertEqual(self.client.get(url).status_code, 302)
        admin = User.objects.create_superuser(
            "template-admin", "template@example.com", "test-password"
        )
        self.client.force_login(admin)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = b"".join(response.streaming_content)
        wb = load_workbook(io.BytesIO(content))
        try:
            sheet = wb["Enseignants"]
            self.assertEqual(
                [c.value for c in sheet[1]][:7],
                ["PPR", "CIN", "Nom", "Prénom", "Email", "Département", "Grade"],
            )
            self.assertEqual(sheet["A2"].number_format, "@")
            self.assertEqual(sheet["B2"].number_format, "@")
            self.assertTrue(all(sheet.cell(r, 1).value is None for r in range(2, 52)))
        finally:
            wb.close()

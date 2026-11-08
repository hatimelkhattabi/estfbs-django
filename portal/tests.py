import io
import json
import tempfile
import sqlite3
from datetime import timedelta
from pathlib import Path
import bcrypt
from PIL import Image
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from .models import (
    Publication,
    Professeur,
    Photo,
    EmploiDuTemps,
    Reglement,
    UploadedDocument,
    DemandeEtudiant,
    DemandePersonnel,
    DemandeVehicule,
    Enseignant,
    SiteVisit,
    Etudiant,
)
from .forms import PublicationForm, ProfesseurForm, PhotoForm, EmploiForm, ReglementForm
from .files import save_document, save_upload
from .richtext import render_content
from .validators import valid_link


def image_upload(name="photo.png"):
    buf = io.BytesIO()
    Image.new("RGB", (40, 50), "navy").save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


def pdf_upload():
    return SimpleUploadedFile(
        "document.pdf",
        b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF",
        content_type="application/pdf",
    )


class PortalTests(TestCase):
    def setUp(self):
        cache.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.override = override_settings(PRIVATE_MEDIA_ROOT=Path(self.tmp.name))
        self.override.enable()
        self.admin = User.objects.create_superuser(
            "admin-test", "admin@example.com", "Strong-Test-Password-2026"
        )

    def tearDown(self):
        self.override.disable()
        self.tmp.cleanup()

    def publication(self, **kw):
        data = {
            "titre": "Avis de test",
            "resume": "Résumé de test",
            "contenu": "Texte",
            "publie": True,
            "date_publication": timezone.now() - timedelta(hours=1),
        }
        data.update(kw)
        return Publication.objects.create(**data)

    def payload(self, **kw):
        data = {
            "titre": "Nouvel avis",
            "resume": "Résumé",
            "contenu": "<p>Bonjour</p>",
            "type": "Actualité",
            "date_publication": timezone.localtime().strftime("%Y-%m-%d %H:%M:%S"),
            "publie": True,
            "texte_bouton": "Consulter le document",
        }
        data.update(kw)
        return data

    def test_public_pages_render_with_shared_header_footer(self):
        for path in [
            "/",
            "/presentation",
            "/actualites",
            "/professeurs.html",
            "/galerie",
            "/emplois-du-temps",
            "/textes-reglements",
            "/organigramme.html",
            "/amphis.html",
            "/administrations.html",
            "/laboratoire.html",
            "/personnel/demande",
            "/suivi.php",
        ]:
            with self.subTest(path=path):
                r = self.client.get(path)
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, "data-site-header", count=1)
                self.assertContains(r, "data-site-footer", count=1)

    def test_presentation_has_sixteen_linked_programmes(self):
        r = self.client.get("/presentation")
        self.assertContains(r, "Agro-énergie")
        self.assertContains(r, "Sciences Agronomique")
        self.assertContains(r, 'href="#"')
        self.assertNotContains(r, "Licence professionnelle")

    def test_home_only_shows_three_publications(self):
        for i in range(6):
            self.publication(titre=f"Unique-publication-{i}")
        html = self.client.get("/").content.decode()
        self.assertEqual(sum(f"Unique-publication-{i}" in html for i in range(6)), 3)
        html = self.client.get("/actualites").content.decode()
        self.assertEqual(sum(f"Unique-publication-{i}" in html for i in range(6)), 6)

    def test_unpublished_and_future_publications_hidden(self):
        for obj in [
            self.publication(publie=False),
            self.publication(date_publication=timezone.now() + timedelta(days=1)),
        ]:
            self.assertEqual(
                self.client.get(f"/publications/{obj.pk}").status_code, 404
            )
            self.assertEqual(
                self.client.get(f"/publications/{obj.pk}?preview=1").status_code, 404
            )
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.get(f"/publications/{obj.pk}?preview=1").status_code, 200
        )

    def test_publication_links_and_filtered_search(self):
        p = self.publication(
            titre="Recherche distinctive",
            type="Événement",
            date_evenement=timezone.localdate(),
        )
        self.assertContains(
            self.client.get("/actualites?q=distinctive"), "Recherche distinctive"
        )
        self.assertNotContains(
            self.client.get("/actualites?type=Actualité"), "Recherche distinctive"
        )
        self.assertContains(
            self.client.get(f"/publications/{p.pk}"), "Recherche distinctive"
        )

    def test_malicious_content_and_delta_are_sanitized(self):
        html = str(
            render_content(
                None,
                '<script>alert(1)</script><p onclick="evil()">Texte</p><a href="javascript:evil()">Lien</a>',
            )
        )
        self.assertNotIn("<script", html)
        self.assertNotIn("onclick", html)
        self.assertNotIn("javascript:", html)
        html = str(
            render_content(
                {
                    "ops": [
                        {"insert": "Titre", "attributes": {"bold": True}},
                        {"insert": "\n", "attributes": {"header": 2}},
                        {"insert": "مرحبا\n", "attributes": {"direction": "rtl"}},
                    ]
                },
                "",
            )
        )
        self.assertIn("<strong>Titre</strong>", html)
        self.assertIn("<h2>", html)
        self.assertIn('dir="rtl"', html)
        self.assertIn(
            "fallback",
            str(
                render_content({"ops": [{"insert": "x", "attributes": []}]}, "fallback")
            ),
        )

    def test_document_private_until_published_reference(self):
        doc = save_document(pdf_upload())
        self.assertEqual(self.client.get(doc.url).status_code, 404)
        p = self.publication(publie=False, lien=doc.url, afficher_bouton=True)
        self.assertEqual(self.client.get(doc.url).status_code, 404)
        p.publie = True
        p.save()
        self.assertEqual(self.client.get(doc.url).status_code, 200)
        p.afficher_bouton = False
        p.save()
        self.assertEqual(self.client.get(doc.url).status_code, 404)
        p.contenu = f'<a href="{doc.url}">PDF</a>'
        p.save()
        self.assertEqual(self.client.get(doc.url).status_code, 200)

    def test_timetable_document_visibility(self):
        doc = save_document(pdf_upload())
        e = EmploiDuTemps.objects.create(filiere="GC", cycle="DUT", lien_s1=doc.url)
        self.assertEqual(self.client.get(doc.url).status_code, 200)
        self.assertContains(self.client.get("/emplois-du-temps"), doc.url)
        e.publie = False
        e.save()
        self.assertEqual(self.client.get(doc.url).status_code, 404)

    def test_upload_requires_admin_and_csrf(self):
        self.assertEqual(
            self.client.post("/admin/documents", {"fichier": pdf_upload()}).status_code,
            403,
        )
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.admin)
        self.assertEqual(
            c.post("/admin/documents", {"fichier": pdf_upload()}).status_code, 403
        )
        c.get("/")
        token = c.cookies["csrftoken"].value
        r = c.post(
            "/admin/documents", {"fichier": pdf_upload()}, HTTP_X_CSRF_TOKEN=token
        )
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.json()["url"].startswith("/documents/"))

    def test_invalid_uploads_rejected(self):
        self.client.force_login(self.admin)
        f = SimpleUploadedFile(
            "attack.png", b"<script>alert(1)</script>", content_type="image/png"
        )
        self.assertEqual(
            self.client.post("/admin/documents", {"fichier": f}).status_code, 422
        )
        for bad in [
            "javascript:alert(1)",
            "//example.com",
            "/../x\\y",
            "https://user:password@example.com",
        ]:
            self.assertFalse(valid_link(bad))

    def test_publication_form_uploads_and_cover(self):
        form = PublicationForm(
            self.payload(afficher_bouton=True),
            {"document_lien": pdf_upload(), "image_upload": image_upload()},
        )
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save()
        self.assertTrue(obj.lien.startswith("/documents/"))
        self.assertTrue(obj.image.startswith("publications/"))
        form = PublicationForm(
            self.payload(
                generer_visuel=True,
                cover_title="LISTE D’ATTENTE",
                cover_subtitle="DBT",
                cover_footer="2026–2027",
            ),
            {"cover_background": image_upload()},
        )
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save()
        with Image.open(Path(self.tmp.name) / obj.image) as image:
            self.assertEqual(image.size, (1000, 600))

    def test_image_and_professor_visibility(self):
        path, _ = save_upload(image_upload(), "publications", "image")
        p = self.publication(image=path, publie=False)
        self.assertEqual(self.client.get(p.image_url).status_code, 404)
        p.publie = True
        p.save()
        self.assertEqual(self.client.get(p.image_url).status_code, 200)
        form = ProfesseurForm(
            {"nom": "TEST", "prenom": "Fatima", "ordre": 0, "publie": True},
            {"photo_upload": image_upload()},
        )
        self.assertTrue(form.is_valid(), form.errors)
        prof = form.save()
        self.assertEqual(self.client.get(prof.photo_url).status_code, 200)
        prof.publie = False
        prof.save()
        self.assertEqual(self.client.get(prof.photo_url).status_code, 404)

    def test_gallery_image_and_video_upload(self):
        form = PhotoForm(
            {"titre": "Image", "type": "image", "ordre": 0, "publie": True},
            {"fichier_upload": image_upload()},
        )
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save()
        self.assertEqual(self.client.get(obj.fichier_url).status_code, 200)
        mp4 = SimpleUploadedFile(
            "test.mp4",
            b"\x00\x00\x00\x18ftypmp42" + b"0" * 32,
            content_type="video/mp4",
        )
        form = PhotoForm(
            {"titre": "Vidéo", "type": "video", "ordre": 1, "publie": True},
            {"fichier_upload": mp4},
        )
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save()
        self.assertContains(self.client.get("/galerie?type=video"), "<video")
        obj.publie = False
        obj.save()
        self.assertEqual(self.client.get(obj.fichier_url).status_code, 404)

    def test_reglement_document_upload(self):
        form = ReglementForm(
            {"titre": "Règlement", "langue": "fr", "ordre": 0, "publie": True},
            {"document": pdf_upload()},
        )
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save()
        self.assertEqual(self.client.get(obj.document_url).status_code, 200)
        obj.publie = False
        obj.save()
        self.assertEqual(self.client.get(obj.document_url).status_code, 404)

    def test_emploi_semester_upload(self):
        form = EmploiForm(
            {
                "filiere": "GC",
                "cycle": "Bachelor",
                "annee": "2026-2027",
                "ordre": 0,
                "publie": True,
            },
            {"fichier_lien_s5": pdf_upload()},
        )
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save()
        self.assertTrue(obj.lien_s5.startswith("/documents/"))
        self.assertEqual(self.client.get(obj.lien_s5).status_code, 200)

    def test_student_personnel_contact_submission_and_tracking(self):
        payload = {
            "nom": "Étudiant Test",
            "cne": "d123",
            "cin": "ab123",
            "filiere": "GI",
            "document": "Attestation",
            "email": "test@example.com",
        }
        self.assertEqual(
            self.client.post("/backend/api/submit_etudiant.php", {}).status_code, 422
        )
        r = self.client.post(
            "/backend/api/submit_etudiant.php",
            json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 201)
        code = r.json()["code_suivi"]
        self.assertRegex(code, r"^ESTFBS-[a-f0-9]{24}$")
        result = self.client.get("/backend/api/check_status.php", {"code": code}).json()
        self.assertTrue(result["success"])
        self.assertNotIn("cin", result["demandes"][0])
        self.assertNotIn("nom_prenom", result["demandes"][0])
        self.assertFalse(
            self.client.get("/backend/api/check_status.php", {"code": "D123"}).json()[
                "success"
            ]
        )
        r = self.client.post(
            "/backend/api/submit_personnel.php",
            {
                "nom": "Personnel",
                "ppr": "P1",
                "fonction": "Technicien",
                "type_attestation": "Travail",
            },
        )
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.json()["code_suivi"].startswith("PERS-"))
        Etudiant.objects.create(apogee="00123456", nom="Test", prenom="Étudiant")
        self.assertEqual(
            self.client.post(
                "/backend/api/submit_contact.php",
                {
                    "nom": "Test",
                    "email": "test@usms.ac.ma",
                    "apogee": "00123456",
                    "sujet": "Question",
                    "message": "Bonjour",
                },
            ).status_code,
            201,
        )

    def test_legacy_tracking_needs_identity(self):
        d = DemandeEtudiant.objects.create(
            code_suivi="ESTFBS-123456",
            nom_prenom="Test",
            cne="D123",
            cin="AB",
            filiere="GI",
            type_document="Attestation",
            email="t@example.com",
        )
        for identity in ["", "WRONG"]:
            self.assertFalse(
                self.client.get(
                    "/backend/api/check_status.php",
                    {"code": d.code_suivi, "identifiant": identity},
                ).json()["success"]
            )
        self.assertTrue(
            self.client.get(
                "/backend/api/check_status.php",
                {"code": d.code_suivi, "identifiant": "D123"},
            ).json()["success"]
        )

    def test_vehicle_request_pdf_and_no_numeric_lookup(self):
        teacher = Enseignant.objects.create(
            utilisateur=User.objects.create_user(
                "enseignant:T001", password="test-Long-2026-password"
            ),
            ppr="T001",
            nom="Professeur Test",
            changer_mot_de_passe=False,
        )
        self.client.force_login(teacher.utilisateur)
        d = {
            "nom_professeur": "Professeur Test",
            "date_visite": (timezone.localdate() + timedelta(days=2)).isoformat(),
            "effectif_etudiants": 24,
            "destination": "Béni Mellal",
            "duree_visite": "Une journée",
            "type_vehicule": "Bus",
            "heure_depart": "08:30",
            "heure_retour": "17:30",
        }
        r = self.client.post(
            "/demande-vehicule",
            json.dumps(d),
            content_type="application/json",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(r.status_code, 201)
        result = r.json()
        self.assertEqual(self.client.get(result["status_url"]).status_code, 200)
        pdf = self.client.get(result["pdf_url"])
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF-"))
        self.assertContains(
            self.client.get("/demande-vehicule/suivi?code=1"), "Aucune demande"
        )

    def test_visitor_statistics(self):
        self.client.get("/")
        r = self.client.get("/api/visitor-stats").json()
        self.assertGreaterEqual(r["total_consultations"], 1)
        self.assertEqual(r["unique_visitors"], 1)
        self.assertEqual(r["data"]["total_consultations"], r["total_consultations"])
        self.client.get("/presentation")
        r = self.client.get("/api/visitor-stats").json()
        self.assertEqual(r["unique_visitors"], 1)
        self.assertEqual(r["visitor_consultations"], 2)

    def test_search_api_only_returns_matching_published_content(self):
        p = self.publication(titre="CISIAI — journée scientifique", type="Événement")
        self.publication(titre="CISIAI brouillon", publie=False)
        self.publication(
            titre="CISIAI futur", date_publication=timezone.now() + timedelta(days=1)
        )
        self.publication(titre="Autre sujet")
        data = self.client.get("/backend/api/publications.php?q=CISIAI").json()["data"]
        self.assertEqual([row["id"] for row in data], [p.pk])
        self.assertEqual(data[0]["url"], f"/publications/{p.pk}")
        self.assertEqual(
            self.client.post("/backend/api/publications.php").status_code, 405
        )

    def test_video_range_requests_and_imported_unsafe_mime(self):
        video = b"\x00\x00\x00\x18ftypmp42" + b"x" * 128
        path, _ = save_upload(
            SimpleUploadedFile("clip.mp4", video, content_type="video/mp4"),
            "gallery",
            "video",
        )
        obj = Photo.objects.create(
            titre="Clip", type="video", fichier=path, publie=True
        )
        response = self.client.get(obj.fichier_url, HTTP_RANGE="bytes=10-19")
        self.assertEqual(response.status_code, 206)
        self.assertEqual(b"".join(response.streaming_content), video[10:20])
        self.assertEqual(response["Content-Range"], f"bytes 10-19/{len(video)}")
        response = self.client.get(obj.fichier_url, HTTP_RANGE="bytes=-5")
        self.assertEqual(b"".join(response.streaming_content), video[-5:])
        self.assertEqual(
            self.client.get(obj.fichier_url, HTTP_RANGE="bytes=10000-").status_code, 416
        )
        bad = Path(self.tmp.name) / "documents/legacy.html"
        bad.parent.mkdir(exist_ok=True)
        bad.write_text("<script>alert(1)</script>")
        doc = UploadedDocument.objects.create(
            path="documents/legacy.html", original_name="legacy.html", mime="text/html"
        )
        self.client.force_login(self.admin)
        response = self.client.get(doc.url)
        self.assertEqual(response["Content-Type"], "application/octet-stream")
        self.assertTrue(response["Content-Disposition"].startswith("attachment"))

    def test_native_admin_publication_crud_and_timetable_upload(self):
        self.client.force_login(self.admin)
        payload = self.payload()
        payload.pop("date_publication")
        payload.update(
            date_publication_0="2026-01-01",
            date_publication_1="12:00:00",
            _save="Enregistrer",
        )
        response = self.client.post("/admin/portal/publication/add/", payload)
        self.assertEqual(response.status_code, 302, response.content[:1000])
        p = Publication.objects.get(titre="Nouvel avis")
        self.assertEqual(self.client.get(f"/publications/{p.pk}").status_code, 200)
        payload["titre"] = "Avis modifié"
        self.assertEqual(
            self.client.post(
                f"/admin/portal/publication/{p.pk}/change/", payload
            ).status_code,
            302,
        )
        p.refresh_from_db()
        self.assertEqual(p.titre, "Avis modifié")
        self.assertEqual(
            self.client.post(
                f"/admin/portal/publication/{p.pk}/delete/", {"post": "yes"}
            ).status_code,
            302,
        )
        self.assertFalse(Publication.objects.filter(pk=p.pk).exists())
        response = self.client.post(
            "/admin/portal/emploidutemps/add/",
            {
                "filiere": "GC",
                "cycle": "DUT",
                "annee": "2026-2027",
                "ordre": 0,
                "publie": "on",
                "fichier_lien_s1": pdf_upload(),
                "_save": "Enregistrer",
            },
        )
        self.assertEqual(response.status_code, 302, response.content[:1000])
        row = EmploiDuTemps.objects.get(filiere="GC")
        self.assertEqual(self.client.get(row.lien_s1).status_code, 200)

    def test_sqlite_import_reads_source_preserves_uuid_and_copies_files(self):
        root = Path(self.tmp.name) / "laravel"
        (root / "storage/app/private/documents").mkdir(parents=True)
        source_file = root / "storage/app/private/documents/old.pdf"
        source_file.write_bytes(b"%PDF-1.4\nOriginal")
        uid = "9600cd90-57e2-4aa2-a4b8-aba837e5d065"
        db = root / "old.sqlite3"
        con = sqlite3.connect(db)
        con.execute(
            "CREATE TABLE uploaded_documents (id TEXT, path TEXT, original_name TEXT, mime TEXT, size INTEGER)"
        )
        con.execute(
            "INSERT INTO uploaded_documents VALUES (?,?,?,?,?)",
            (
                uid,
                "documents/old.pdf",
                "ancien.pdf",
                "application/pdf",
                source_file.stat().st_size,
            ),
        )
        con.execute(
            "CREATE TABLE emplois_du_temps (id INTEGER, filiere TEXT, cycle TEXT, annee TEXT, lien_s1 TEXT, publie INTEGER)"
        )
        con.execute(
            "INSERT INTO emplois_du_temps VALUES (1,?,?,?,?,1)",
            ("GC", "DUT", "2026-2027", "/documents/" + uid),
        )
        con.commit()
        con.close()
        before = db.read_bytes()
        call_command("import_laravel", sqlite=db, files=root, stdout=io.StringIO())
        self.assertEqual(db.read_bytes(), before)
        self.assertEqual(source_file.read_bytes(), b"%PDF-1.4\nOriginal")
        self.assertEqual(self.client.get("/documents/" + uid).status_code, 200)
        self.assertTrue(UploadedDocument.objects.filter(pk=uid).exists())

    def test_bcrypt_legacy_account_rehashes_on_login(self):
        hashed = (
            bcrypt.hashpw(b"Legacy-Test-Password-2026", bcrypt.gensalt(rounds=4))
            .decode()
            .replace("$2b$", "$2y$", 1)
        )
        u = User.objects.create(
            username="legacy", password="laravel_bcrypt$" + hashed, is_staff=True
        )
        self.assertIsNotNone(
            authenticate(username="legacy", password="Legacy-Test-Password-2026")
        )
        u.refresh_from_db()
        self.assertTrue(u.password.startswith("pbkdf2_sha256$"))

    def test_admin_pages_and_permissions(self):
        self.assertEqual(self.client.get("/admin/portal/publication/").status_code, 302)
        ordinary = User.objects.create_user("ordinary", password="Strong-Test-2026")
        self.client.force_login(ordinary)
        self.assertEqual(self.client.get("/admin/portal/publication/").status_code, 302)
        self.client.force_login(self.admin)
        for model in [
            "publication",
            "professeur",
            "photo",
            "emploidutemps",
            "reglement",
            "demandeetudiant",
            "demandepersonnel",
            "messagecontact",
            "demandevehicule",
        ]:
            for suffix in ["", "add/"]:
                with self.subTest(model=model, suffix=suffix):
                    self.assertEqual(
                        self.client.get(f"/admin/portal/{model}/{suffix}").status_code,
                        200,
                    )

    def test_seed_idempotent_and_import_updates(self):
        call_command("seed_site", stdout=io.StringIO())
        counts = (
            Publication.objects.count(),
            Professeur.objects.count(),
            Photo.objects.count(),
            EmploiDuTemps.objects.count(),
        )
        self.assertEqual(counts, (4, 26, 9, 16))
        call_command("seed_site", stdout=io.StringIO())
        self.assertEqual(
            counts,
            (
                Publication.objects.count(),
                Professeur.objects.count(),
                Photo.objects.count(),
                EmploiDuTemps.objects.count(),
            ),
        )
        path = Path(self.tmp.name) / "import.json"
        path.write_text(
            json.dumps(
                {
                    "actualites_evenements": [
                        {
                            "id": 1,
                            "titre": "Titre importé",
                            "resume": "Résumé",
                            "contenu": "Texte",
                            "publie": 1,
                            "date_publication": "2026-01-01 10:00:00",
                        }
                    ]
                }
            )
        )
        call_command("import_laravel", json=path, stdout=io.StringIO())
        self.assertEqual(Publication.objects.get(pk=1).titre, "Titre importé")
        self.assertEqual(Publication.objects.count(), 4)

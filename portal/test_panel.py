"""Parcours réels du panneau EST-FBS personnalisé."""

import io
import json
import tempfile
from datetime import timedelta
from pathlib import Path

from django.contrib.auth.models import User, Permission
from django.core.cache import cache
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from .tests import image_upload, pdf_upload
from .models import (
    Publication,
    Professeur,
    Photo,
    EmploiDuTemps,
    Reglement,
    DemandeEtudiant,
    DemandePersonnel,
    MessageContact,
    DemandeVehicule,
)
from .richtext import render_content


def design():
    return {
        "version": 1,
        "background": "custom",
        "backgroundColor": "#f5eee3",
        "veil": 20,
        "cropX": 50,
        "cropY": 50,
        "logo": {"visible": False, "source": "default", "x": 50, "y": 21, "width": 14},
        "texts": [
            {
                "id": "text-title",
                "text": "LISTE D’ATTENTE",
                "x": 50,
                "y": 53,
                "size": 110,
                "width": 84,
                "font": "outfit",
                "bold": True,
                "color": "#18202b",
                "align": "center",
            }
        ],
    }


class AdminReplicaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.override = override_settings(PRIVATE_MEDIA_ROOT=Path(self.tmp.name))
        self.override.enable()
        self.user = User.objects.create_superuser(
            "hatim-test", "test@example.com", "Strong-Admin-Password-2026!"
        )
        self.client.force_login(self.user)

    def tearDown(self):
        self.override.disable()
        self.tmp.cleanup()

    def publication_data(self, **kw):
        data = {
            "titre": "Publication personnalisée",
            "resume": "Résumé",
            "contenu": "<p>Contenu complet</p>",
            "type": "Actualité",
            "date_publication": "2026-01-01T10:30",
            "publie": "1",
            "texte_bouton": "Consulter le document",
        }
        data.update(kw)
        return data

    def test_original_login_and_safe_redirects(self):
        self.client.logout()
        r = self.client.get("/admin/login/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Espace Scolarité & Administration")
        self.assertContains(r, "nodes-canvas")
        self.assertNotContains(r, 'id="nav-sidebar"')
        r = self.client.post(
            "/admin/login/", {"username": "hatim-test", "password": "wrong"}
        )
        self.assertContains(r, 'role="alert"')
        self.assertNotIn("_auth_user_id", self.client.session)
        r = self.client.post(
            "/admin/login/",
            {
                "username": "hatim-test",
                "password": "Strong-Admin-Password-2026!",
                "next": "https://evil.example/",
            },
        )
        self.assertRedirects(r, "/admin/", fetch_redirect_response=False)
        self.assertEqual(self.client.get("/admin/logout/").status_code, 405)
        self.assertRedirects(
            self.client.post("/admin/logout/"),
            "/admin/login/",
            fetch_redirect_response=False,
        )

    def test_all_old_lists_and_forms_empty_then_populated(self):
        modules = [
            "publications",
            "professeurs",
            "photos",
            "emplois-du-temps",
            "textes-reglements",
        ]
        for mode in ("empty", "seeded"):
            if mode == "seeded":
                call_command("seed_site", stdout=io.StringIO())
            for module in modules:
                for suffix in ("", "/create"):
                    with self.subTest(mode=mode, module=module, suffix=suffix):
                        r = self.client.get("/admin/" + module + suffix)
                        self.assertEqual(r.status_code, 200)
                        self.assertContains(r, 'class="pub-sidebar"')
                        self.assertNotContains(r, 'id="nav-sidebar"')
            self.assertEqual(self.client.get("/admin/").status_code, 200)
        for module, model in [
            ("publications", Publication),
            ("professeurs", Professeur),
            ("photos", Photo),
            ("emplois-du-temps", EmploiDuTemps),
            ("textes-reglements", Reglement),
        ]:
            self.assertEqual(
                self.client.get(
                    f"/admin/{module}/{model.objects.first().pk}/edit"
                ).status_code,
                200,
            )

    def test_custom_publication_create_edit_preview_toggle_delete(self):
        data = self.publication_data(
            image=image_upload(),
            document_lien=pdf_upload(),
            afficher_bouton="1",
            bouton_nouvel_onglet="1",
            contenu_delta=json.dumps(
                {
                    "ops": [
                        {"insert": "Bonjour", "attributes": {"bold": True}},
                        {"insert": "\n"},
                    ]
                }
            ),
        )
        self.assertRedirects(
            self.client.post("/admin/publications/create", data),
            "/admin/publications",
            fetch_redirect_response=False,
        )
        obj = Publication.objects.get()
        self.assertTrue(obj.publie)
        self.assertTrue(obj.lien.startswith("/documents/"))
        self.assertTrue(obj.image.startswith("publications/"))
        self.assertContains(
            self.client.get(f"/publications/{obj.pk}"),
            "<strong>Bonjour</strong>",
            html=True,
        )
        r = self.client.post(
            f"/admin/publications/{obj.pk}/edit",
            self.publication_data(
                titre="Publication modifiée", publie="0", texte_bouton=""
            ),
        )
        self.assertEqual(r.status_code, 302)
        obj.refresh_from_db()
        self.assertFalse(obj.publie)
        self.assertEqual(obj.titre, "Publication modifiée")
        self.assertEqual(
            self.client.get(f"/publications/{obj.pk}?preview=1").status_code, 200
        )
        self.assertEqual(
            self.client.get(f"/admin/publications/{obj.pk}/toggle").status_code, 405
        )
        self.assertEqual(
            self.client.post(f"/admin/publications/{obj.pk}/toggle").status_code, 302
        )
        obj.refresh_from_db()
        self.assertTrue(obj.publie)
        self.assertEqual(
            self.client.post(f"/admin/publications/{obj.pk}/destroy").status_code, 302
        )
        self.assertFalse(Publication.objects.exists())

    def test_validation_retains_user_inputs(self):
        data = self.publication_data(
            titre="<script>input</script>",
            resume="",
            afficher_bouton="1",
            lien="javascript:alert(1)",
        )
        r = self.client.post("/admin/publications/create", data)
        self.assertEqual(r.status_code, 422)
        self.assertContains(r, "&lt;script&gt;input&lt;/script&gt;", status_code=422)
        self.assertFalse(Publication.objects.exists())

    def test_composer_saves_private_sources_and_ignores_supplied_paths(self):
        composition = design()
        composition["backgroundAsset"] = "../../.env"
        data = self.publication_data(
            cover_design=json.dumps(composition),
            image=image_upload("cover.png"),
            cover_background=image_upload("background.png"),
        )
        r = self.client.post("/admin/publications/create", data)
        self.assertEqual(r.status_code, 302)
        obj = Publication.objects.get()
        self.assertTrue(obj.cover_design["backgroundAsset"].startswith("covers/"))
        self.assertNotIn("..", obj.cover_design["backgroundAsset"])
        self.assertEqual(
            self.client.get(
                f"/admin/publications/{obj.pk}/cover-assets/background"
            ).status_code,
            200,
        )
        self.assertNotContains(
            self.client.get(f"/admin/publications/{obj.pk}/edit"), "data-cover-canvas"
        )
        self.assertContains(
            self.client.get(f"/admin/createur-images?publication={obj.pk}"),
            "data-cover-canvas",
        )
        r = self.client.post(
            f"/admin/publications/{obj.pk}/edit",
            self.publication_data(
                cover_design=json.dumps(design()), image=image_upload("new.png")
            ),
        )
        self.assertEqual(r.status_code, 302)
        obj.refresh_from_db()
        self.assertIn("backgroundAsset", obj.cover_design)
        self.client.logout()
        self.assertEqual(
            self.client.get(
                f"/admin/publications/{obj.pk}/cover-assets/background"
            ).status_code,
            302,
        )

    def test_composer_refuses_missing_sources_and_invalid_settings(self):
        for composition in [
            design(),
            dict(design(), veil=1000),
            dict(design(), texts=[{"text": "bad"}]),
        ]:
            r = self.client.post(
                "/admin/publications/create",
                self.publication_data(
                    cover_design=json.dumps(composition), image=image_upload()
                ),
            )
            self.assertEqual(r.status_code, 422)
            self.assertFalse(Publication.objects.exists())

    def test_professor_and_gallery_crud(self):
        self.assertEqual(
            self.client.post(
                "/admin/professeurs/create",
                {
                    "nom": "TEST",
                    "prenom": "Fatima",
                    "ordre": 2,
                    "publie": "1",
                    "photo": image_upload(),
                },
            ).status_code,
            302,
        )
        p = Professeur.objects.get()
        self.assertTrue(p.photo)
        self.assertEqual(self.client.get(p.photo_url).status_code, 200)
        self.assertEqual(
            self.client.post(
                f"/admin/professeurs/{p.pk}/edit",
                {
                    "nom": "TEST",
                    "prenom": "Fatima",
                    "ordre": 2,
                    "publie": "0",
                    "remove_photo": "1",
                },
            ).status_code,
            302,
        )
        p.refresh_from_db()
        self.assertFalse(p.photo)
        self.assertFalse(p.publie)
        self.assertEqual(
            self.client.post(
                "/admin/photos/create",
                {
                    "titre": "Campus",
                    "type": "image",
                    "ordre": 0,
                    "publie": "1",
                    "fichier": image_upload(),
                    "vignette": image_upload(),
                },
            ).status_code,
            302,
        )
        m = Photo.objects.get()
        self.assertTrue(m.vignette)
        self.assertEqual(
            self.client.post(
                f"/admin/photos/{m.pk}/edit",
                {
                    "titre": "Campus modifié",
                    "type": "image",
                    "ordre": 1,
                    "publie": "0",
                    "remove_vignette": "1",
                },
            ).status_code,
            302,
        )
        m.refresh_from_db()
        self.assertFalse(m.vignette)
        self.assertFalse(m.publie)
        for module, obj in [("professeurs", p), ("photos", m)]:
            self.assertEqual(
                self.client.post(f"/admin/{module}/{obj.pk}/toggle").status_code, 302
            )
            self.assertEqual(
                self.client.post(f"/admin/{module}/{obj.pk}/destroy").status_code, 302
            )

    def test_timetable_and_reglement_uploads(self):
        r = self.client.post(
            "/admin/emplois-du-temps/create",
            {
                "filiere": "GC",
                "cycle": "DUT",
                "annee": "2026-2027",
                "ordre": 0,
                "publie": "1",
                "fichier_s1": pdf_upload(),
            },
        )
        self.assertEqual(r.status_code, 302)
        e = EmploiDuTemps.objects.get()
        self.assertEqual(self.client.get(e.lien_s1).status_code, 200)
        old = e.lien_s1
        self.assertEqual(
            self.client.post(
                f"/admin/emplois-du-temps/{e.pk}/edit",
                {
                    "filiere": "GC",
                    "cycle": "Bachelor",
                    "annee": "2026-2027",
                    "ordre": 0,
                    "publie": "1",
                    "fichier_s5": pdf_upload(),
                },
            ).status_code,
            302,
        )
        e.refresh_from_db()
        self.assertEqual(e.lien_s1, old)
        self.assertTrue(e.lien_s5)
        r = self.client.post(
            "/admin/textes-reglements/create",
            {
                "titre": "Nouveau règlement",
                "langue": "fr",
                "ordre": 0,
                "publie": "1",
                "fichier": pdf_upload(),
            },
        )
        self.assertEqual(r.status_code, 302)
        reg = Reglement.objects.get()
        self.assertEqual(self.client.get(reg.document_url).status_code, 200)
        for module, obj in [("emplois-du-temps", e), ("textes-reglements", reg)]:
            self.assertEqual(
                self.client.post(f"/admin/{module}/{obj.pk}/toggle").status_code, 302
            )
            self.assertEqual(
                self.client.post(f"/admin/{module}/{obj.pk}/destroy").status_code, 302
            )

    def test_video_upload_and_original_editor_fields(self):
        video = SimpleUploadedFile(
            "clip.mp4",
            b"\x00\x00\x00\x18ftypmp42" + b"x" * 128,
            content_type="video/mp4",
        )
        r = self.client.post(
            "/admin/photos/create",
            {
                "titre": "Vidéo campus",
                "type": "video",
                "ordre": 1,
                "publie": "1",
                "fichier": video,
            },
        )
        self.assertEqual(r.status_code, 302)
        obj = Photo.objects.get()
        self.assertContains(self.client.get(f"/admin/photos/{obj.pk}/edit"), "<video")
        self.assertEqual(
            self.client.get(obj.fichier_url, HTTP_RANGE="bytes=0-9").status_code, 206
        )
        html = self.client.get("/admin/publications/create")
        for element in [
            "publication-rich-editor",
            "publication-rich-toolbar",
            "publication-link-dialog",
            "/admin/createur-images",
            "suppression_apres_jours",
        ]:
            self.assertContains(html, element)
        self.assertContains(html, "/static/vendor/quill/quill.js")

    def test_dashboard_statuses_search_and_private_data(self):
        s = DemandeEtudiant.objects.create(
            nom_prenom="Étudiant unique",
            cne="D123",
            cin="AB",
            filiere="GI",
            type_document="Attestation",
            email="s@example.com",
        )
        p = DemandePersonnel.objects.create(
            nom_prenom="Personnel",
            ppr="P1",
            fonction="Technicien",
            type_attestation="Travail",
        )
        m = MessageContact.objects.create(
            nom_complet="Visiteur",
            email="v@example.com",
            sujet="Question",
            message="Test",
        )
        v = DemandeVehicule.objects.create(
            nom_professeur="Professeur",
            date_visite=timezone.localdate(),
            effectif_etudiants=20,
            destination="Béni Mellal",
            duree_visite="Un jour",
        )
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        self.assertContains(self.client.get("/admin/?q=unique"), "Étudiant unique")
        for action, obj, status in [
            ("update_status_etudiant", s, "Prête"),
            ("update_status_pers", p, "Prête"),
            ("update_message_status", m, "Traité"),
            ("update_vehicle_status", v, "Validée"),
        ]:
            response = self.client.post(
                "/admin/",
                {
                    "action": action,
                    "id": obj.pk,
                    "status": status,
                    "remarque_administration": "Validé",
                },
            )
            self.assertEqual(response.status_code, 302)
            obj.refresh_from_db()
            self.assertEqual(obj.statut, status)
        self.assertEqual(
            self.client.post(
                "/admin/",
                {"action": "update_status_etudiant", "id": s.pk, "status": "injected"},
            ).status_code,
            400,
        )
        self.client.logout()
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(b"\xc3\x89tudiant unique", response.content)

    def test_permissions_and_csrf_enforced(self):
        readonly = User.objects.create_user(
            "reader", password="Reader-2026", is_staff=True
        )
        readonly.user_permissions.add(
            Permission.objects.get(
                codename="view_publication", content_type__app_label="portal"
            )
        )
        c = Client()
        c.force_login(readonly)
        self.assertEqual(c.get("/admin/publications").status_code, 200)
        self.assertEqual(
            c.post("/admin/documents", {"fichier": pdf_upload()}).status_code, 403
        )
        for method, path in [
            ("get", "/admin/publications/create"),
            ("post", "/admin/publications/create"),
            ("get", "/admin/professeurs"),
        ]:
            self.assertEqual(getattr(c, method)(path).status_code, 403)
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.user)
        self.assertEqual(
            c.post("/admin/publications/create", self.publication_data()).status_code,
            403,
        )
        c.get("/admin/publications/create")
        token = c.cookies["csrftoken"].value
        self.assertEqual(
            c.post(
                "/admin/publications/create",
                self.publication_data(),
                HTTP_X_CSRF_TOKEN=token,
            ).status_code,
            302,
        )

    def test_filters_pagination_and_quill_formatting(self):
        for i in range(24):
            Publication.objects.create(
                titre=f"Rapport {i}",
                resume="Résumé",
                publie=True,
                date_publication=timezone.now() - timedelta(days=1),
            )
        Publication.objects.create(
            titre="Brouillon spécial", resume="Résumé", publie=False
        )
        r = self.client.get("/admin/publications?page=2")
        self.assertContains(r, "Page 2 / 2")
        self.assertContains(
            self.client.get("/admin/publications?statut=brouillon"), "Brouillon spécial"
        )
        self.assertNotContains(
            self.client.get("/admin/publications?statut=publie"), "Brouillon spécial"
        )
        html = str(
            render_content(
                {
                    "ops": [
                        {
                            "insert": "Texte",
                            "attributes": {"font": "serif", "size": "large"},
                        },
                        {"insert": "\n", "attributes": {"direction": "rtl"}},
                    ]
                }
            )
        )
        self.assertIn("ql-font-serif", html)
        self.assertIn("ql-size-large", html)
        self.assertIn('dir="rtl"', html)

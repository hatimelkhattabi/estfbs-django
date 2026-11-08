import json
import re
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from .models import DemandeVehicule, Enseignant
from .pdf import mission_pdf, vehicle_pdf
from .vehicle_documents import document_tree


class VehicleApprovalTests(TestCase):
    def setUp(self):
        cache.clear()
        self.teacher = Enseignant.objects.create(
            utilisateur=User.objects.create_user(
                "enseignant:TEST001", password="Original-test-password!2026"
            ),
            ppr="TEST001",
            nom="Pr. Test Enseignant",
            grade="PES",
            changer_mot_de_passe=False,
        )
        self.client.force_login(self.teacher.utilisateur)
        self.obj = DemandeVehicule.objects.create(
            enseignant=self.teacher,
            nom_professeur="Pr. Enseignant de test",
            date_visite=timezone.localdate() + timedelta(days=5),
            effectif_etudiants=25,
            destination="Rabat - Laboratoire",
            duree_visite="Une journée complète",
        )
        self.status_url = f"/demande-vehicule/{self.obj.code_suivi}"
        self.mission_url = self.status_url + "/ordre-mission-pdf"
        self.pdf_url = self.status_url + "/pdf"

    def pages(self, content):
        return len(re.findall(rb"/Type\s*/Page\b", content))

    def change_status(self, status):
        self.obj.statut = status
        self.obj.save()

    def test_all_unapproved_statuses_block_inline_and_download(self):
        for status in [
            "En cours de traitement",
            "Rejetée",
            "Refusée",
            "",
            "Validée ",
            "Autre",
        ]:
            self.change_status(status)
            for query in [
                {},
                {"download": "1"},
                {"download": "1", "statut": "Validée", "approved": "true"},
            ]:
                with self.subTest(status=status, query=query):
                    response = self.client.get(self.mission_url, query)
                    self.assertEqual(response.status_code, 403)
                    self.assertNotEqual(response["Content-Type"], "application/pdf")
                    self.assertNotIn("Content-Disposition", response)
                    self.assertEqual(response["Cache-Control"], "private, no-store")
                    self.assertEqual(response["Referrer-Policy"], "no-referrer")

    def test_pending_request_pdf_does_not_include_mission(self):
        with patch(
            "portal.pdf.mission_story",
            side_effect=AssertionError("Mission generated before approval"),
        ):
            response = self.client.get(self.pdf_url + "?download=1")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "application/pdf")
            self.assertEqual(self.pages(response.content), 1)
            self.assertEqual(self.pages(vehicle_pdf(self.obj)), 1)
        tree = document_tree(self.obj, "pdf")
        self.assertIsNone(tree.find("page-ordre-mission"))

    def test_generator_itself_rejects_unapproved_mission(self):
        with self.assertRaises(PermissionDenied):
            mission_pdf(self.obj)
        with self.assertRaises(PermissionDenied):
            document_tree(self.obj, "ordre-mission-pdf")

    def test_public_views_reveal_mission_links_only_after_approval(self):
        for status, allowed in [
            ("En cours de traitement", False),
            ("Refusée", False),
            ("Validée", True),
            ("Approuvée", True),
        ]:
            self.change_status(status)
            for url in [
                self.status_url,
                "/demande-vehicule/suivi?code=" + self.obj.code_suivi,
            ]:
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                if allowed:
                    self.assertContains(response, self.mission_url)
                    self.assertContains(response, "Télécharger Demande + Ordre")
                else:
                    self.assertNotContains(response, self.mission_url)
                    self.assertContains(response, "la demande doit être validée")
                    self.assertContains(response, "Télécharger la demande (PDF)")

    def test_both_approved_statuses_release_both_documents(self):
        for status in ["Validée", "Approuvée"]:
            self.change_status(status)
            for url, pages in [(self.mission_url, 1), (self.pdf_url, 2)]:
                for suffix, disposition in [
                    ("", "inline"),
                    ("?download=1", "attachment"),
                ]:
                    response = self.client.get(url + suffix)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(self.pages(response.content), pages)
                    self.assertIn(disposition, response["Content-Disposition"])
                    self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_revocation_blocks_old_links_and_removes_mission_from_combined_pdf(self):
        self.change_status("Validée")
        self.assertEqual(self.client.get(self.mission_url).status_code, 200)
        self.change_status("Rejetée")
        self.assertEqual(
            self.client.get(self.mission_url + "?download=1").status_code, 403
        )
        self.assertEqual(self.pages(self.client.get(self.pdf_url).content), 1)
        self.assertNotContains(self.client.get(self.status_url), self.mission_url)

    def test_submission_and_legacy_endpoint_cannot_self_approve(self):
        payload = {
            "nom_professeur": "Pr. Autre Enseignant",
            "date_visite": self.obj.date_visite.isoformat(),
            "effectif_etudiants": 20,
            "destination": "Casablanca",
            "duree_visite": "Une journée",
            "statut": "Approuvée",
            "ordre_mission_disponible": True,
        }
        for url in [
            "/demande-vehicule",
            "/professeur/demande-vehicule",
            "/demande-vehicule/ordre-mission-pdf",
        ]:
            response = self.client.post(
                url, json.dumps(payload), content_type="application/json"
            )
            self.assertEqual(response.status_code, 201)
            result = response.json()
            self.assertEqual(result["statut"], "En cours de traitement")
            self.assertFalse(result["ordre_mission_disponible"])
            self.assertIsNone(result["ordre_mission_download_url"])
            self.assertIsNone(result["ordre_mission_pdf_url"])
            self.assertEqual(
                self.client.get(
                    result["status_url"] + "/ordre-mission-pdf"
                ).status_code,
                403,
            )
        self.assertEqual(DemandeVehicule.objects.filter(statut="Approuvée").count(), 0)
        self.assertEqual(
            self.client.post(self.status_url, {"statut": "Validée"}).status_code, 405
        )

    def test_admin_must_save_approved_status_before_document_is_available(self):
        admin = User.objects.create_superuser(
            "approver", "approver@example.com", "Strong-test-password"
        )
        self.client.force_login(admin)
        self.assertEqual(self.client.get(self.mission_url).status_code, 403)
        self.assertNotContains(
            self.client.get("/admin/?tab=vehicules"), self.mission_url
        )
        self.assertEqual(
            self.client.post(
                "/admin/",
                {
                    "action": "update_vehicle_status",
                    "id": self.obj.pk,
                    "status": "Validée",
                },
            ).status_code,
            302,
        )
        self.assertContains(self.client.get("/admin/?tab=vehicules"), self.mission_url)
        self.client.logout()
        self.client.force_login(self.teacher.utilisateur)
        self.assertEqual(self.client.get(self.mission_url).status_code, 200)

    def test_staff_without_change_permission_cannot_approve(self):
        staff = User.objects.create_user(
            "viewer", password="Strong-test-password", is_staff=True
        )
        staff.user_permissions.add(
            Permission.objects.get(codename="view_demandevehicule")
        )
        self.client.force_login(staff)
        response = self.client.post(
            "/admin/",
            {"action": "update_vehicle_status", "id": self.obj.pk, "status": "Validée"},
        )
        self.assertEqual(response.status_code, 403)
        self.obj.refresh_from_db()
        self.assertFalse(self.obj.ordre_mission_disponible)
        self.assertEqual(self.client.get(self.mission_url).status_code, 403)

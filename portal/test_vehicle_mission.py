import json
import re
from datetime import timedelta
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase
from django.utils import timezone
from .forms import VehicleForm
from .models import DemandeVehicule, EmploiDuTemps, Enseignant


class VehicleMissionTests(TestCase):
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
        self.depart = timezone.localdate() + timedelta(days=5)
        self.payload = dict(
            nom_professeur="Pr. Test Enseignant",
            date_visite=self.depart.isoformat(),
            destination="Casablanca - Site de visite",
            duree_visite="Une journée complète",
            effectif_etudiants=38,
        )

    def post(self, **changes):
        return self.client.post(
            "/demande-vehicule",
            json.dumps(self.payload | changes),
            content_type="application/json",
        )

    def test_source_form_and_current_programmes(self):
        EmploiDuTemps.objects.create(
            filiere="Génie Informatique", cycle="DUT", annee="2026-2027", publie=True
        )
        response = self.client.get("/demande-vehicule")
        for text in [
            "Affectation de Véhicule",
            'name="grade_professeur"',
            "DUT Génie Informatique",
            "Math - Informatiques",
            "Biotechnologie Agroalimentaire",
            "Ordre de mission après validation",
        ]:
            self.assertContains(response, text)
        for grade in ["PA", "PH", "PES"]:
            self.assertContains(response, f'value="{grade}"')
        self.assertNotContains(response, "Type de véhicule souhaité")

    def test_submission_defaults_and_cannot_forge_status(self):
        response = self.post(statut="Validée", code_suivi="FORGED")
        self.assertEqual(response.status_code, 201)
        obj = DemandeVehicule.objects.get()
        self.assertEqual(obj.grade_professeur, "PES")
        self.assertEqual(obj.organisme_accueil, obj.destination)
        self.assertEqual(obj.date_retour, self.depart)
        self.assertEqual((obj.heure_depart, obj.heure_retour), ("08:30", "17:30"))
        self.assertEqual(obj.type_vehicule, "Grand Bus Universitaire (50 places)")
        self.assertEqual(obj.statut, "En cours de traitement")
        self.assertRegex(obj.code_suivi, r"^ESTFBS-VEH-\d{4}-[A-F0-9]{24}$")
        for key in [
            "pdf_url",
            "pdf_download_url",
            "status_url",
        ]:
            self.assertTrue(response.json()[key].startswith("/demande-vehicule/"))
        self.assertFalse(response.json()["ordre_mission_disponible"])
        self.assertIsNone(response.json()["ordre_mission_pdf_url"])
        self.assertIsNone(response.json()["ordre_mission_download_url"])

    def test_vehicle_selection_boundaries(self):
        for count, label in [
            (1, "Véhicule"),
            (6, "Véhicule"),
            (7, "Minibus"),
            (25, "Minibus"),
            (26, "Grand Bus"),
            (50, "Grand Bus"),
            (51, "Autocar"),
            (150, "Autocar"),
        ]:
            form = VehicleForm(self.payload | {"effectif_etudiants": count})
            self.assertTrue(form.is_valid(), form.errors)
            self.assertTrue(form.cleaned_data["type_vehicule"].startswith(label))

    def test_return_dates_and_explicit_details(self):
        for duration, days in [
            ("2 jours consécutifs", 1),
            ("3 jours ou plus (mission spéciale)", 2),
        ]:
            form = VehicleForm(self.payload | {"duree_visite": duration})
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(
                form.cleaned_data["date_retour"], self.depart + timedelta(days=days)
            )
        self.teacher.grade = "PH"
        self.teacher.save()
        response = self.post(
            date_retour=(self.depart + timedelta(days=6)).isoformat(),
            grade_professeur="PH",
            organisme_accueil="Laboratoire d’accueil",
        )
        self.assertEqual(response.status_code, 201)
        obj = DemandeVehicule.objects.get()
        self.assertEqual(
            (obj.grade_professeur, obj.organisme_accueil),
            ("PH", "Laboratoire d’accueil"),
        )
        self.assertEqual(obj.date_retour, self.depart + timedelta(days=6))

    def test_invalid_dates_times_capacity_and_names(self):
        for values, field in [
            (
                {"date_retour": (self.depart - timedelta(days=1)).isoformat()},
                "date_retour",
            ),
            ({"heure_depart": "17:00", "heure_retour": "08:00"}, "heure_retour"),
            ({"heure_depart": "25:99"}, "heure_depart"),
            ({"effectif_etudiants": 151}, "effectif_etudiants"),
            ({"effectif_etudiants": 0}, "effectif_etudiants"),
            (
                {"date_visite": (timezone.localdate() - timedelta(days=1)).isoformat()},
                "date_visite",
            ),
        ]:
            response = self.post(**values)
            self.assertEqual(response.status_code, 422)
            self.assertIn(field, response.json()["errors"])
        self.assertEqual(DemandeVehicule.objects.count(), 0)

    def test_html_fallback_keeps_values_and_redirects(self):
        response = self.client.post(
            "/demande-vehicule", self.payload | {"destination": ""}
        )
        self.assertContains(response, "Pr. Test Enseignant", status_code=422)
        response = self.client.post("/demande-vehicule", self.payload)
        self.assertEqual(response.status_code, 302)
        self.assertIn(DemandeVehicule.objects.get().code_suivi, response.url)

    def test_pdf_pages_downloads_and_private_headers(self):
        result = self.post().json()
        obj = DemandeVehicule.objects.get()
        obj.statut = "Validée"
        obj.save()
        result["ordre_mission_pdf_url"] = result["status_url"] + "/ordre-mission-pdf"
        for key, pages in [("pdf_url", 2), ("ordre_mission_pdf_url", 1)]:
            response = self.client.get(result[key])
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.content.startswith(b"%PDF-"))
            self.assertEqual(response["Content-Type"], "application/pdf")
            self.assertEqual(
                len(re.findall(rb"/Type\s*/Page\b", response.content)), pages
            )
            self.assertIn("inline", response["Content-Disposition"])
            self.assertEqual(response["Cache-Control"], "private, no-store")
            self.assertIn(
                "attachment",
                self.client.get(result[key] + "?download=1")["Content-Disposition"],
            )

    def test_long_text_is_kept_in_annex(self):
        result = self.post(
            motif_visite="Texte détaillé " * 180, accompagnateurs="Accompagnateur " * 60
        ).json()
        obj = DemandeVehicule.objects.get()
        obj.statut = "Approuvée"
        obj.save()
        response = self.client.get(result["status_url"] + "/ordre-mission-pdf")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(
            len(re.findall(rb"/Type\s*/Page\b", response.content)), 2
        )

    def test_legacy_direct_submission_registers_pending_request(self):
        response = self.client.post("/demande-vehicule/ordre-mission-pdf", self.payload)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/demande-vehicule/", response.url)
        self.assertEqual(DemandeVehicule.objects.count(), 1)
        self.assertFalse(DemandeVehicule.objects.get().ordre_mission_disponible)
        self.assertEqual(
            self.client.get("/demande-vehicule/ordre-mission-pdf").status_code, 405
        )
        self.assertEqual(
            self.client.post(
                "/demande-vehicule/ordre-mission-pdf",
                {},
                HTTP_ACCEPT="application/json",
            ).status_code,
            422,
        )
        self.assertEqual(DemandeVehicule.objects.count(), 1)

    def test_status_and_no_numeric_lookup(self):
        result = self.post().json()
        obj = DemandeVehicule.objects.get()
        obj.statut = "Validée"
        obj.remarque_administration = "Confirmation du service transport"
        obj.save()
        response = self.client.get(result["status_url"])
        self.assertContains(response, "Validée")
        self.assertContains(response, "Confirmation du service transport")
        self.assertContains(response, "ordre-mission-pdf")
        self.assertEqual(
            self.client.get(
                f"/demande-vehicule/{obj.pk}/ordre-mission-pdf"
            ).status_code,
            404,
        )
        self.assertContains(
            self.client.get("/demande-vehicule/suivi", {"code": str(obj.pk)}),
            "Aucune demande",
        )

    def test_csrf_on_both_submission_routes(self):
        client = Client(enforce_csrf_checks=True)
        for path in ["/demande-vehicule", "/demande-vehicule/ordre-mission-pdf"]:
            self.assertEqual(client.post(path, self.payload).status_code, 403)
        client.force_login(self.teacher.utilisateur)
        client.get("/demande-vehicule")
        self.assertEqual(
            client.post(
                "/demande-vehicule",
                self.payload,
                HTTP_X_CSRF_TOKEN=client.cookies["csrftoken"].value,
            ).status_code,
            302,
        )

    def test_admin_document_links_and_status_change(self):
        result = self.post().json()
        obj = DemandeVehicule.objects.get()
        admin = User.objects.create_superuser(
            "mission-admin", "admin@example.com", "Long-test-password"
        )
        self.client.force_login(admin)
        mission_url = result["status_url"] + "/ordre-mission-pdf"
        self.assertNotContains(
            self.client.get("/admin/", {"tab": "vehicules"}),
            mission_url,
        )
        self.assertEqual(
            self.client.post(
                "/admin/",
                {
                    "action": "update_vehicle_status",
                    "id": obj.pk,
                    "status": "Approuvée",
                    "remarque_administration": "Disponible",
                },
            ).status_code,
            302,
        )
        obj.refresh_from_db()
        self.assertEqual(obj.statut, "Approuvée")
        self.assertContains(
            self.client.get("/admin/", {"tab": "vehicules"}), mission_url
        )
        self.assertEqual(self.client.get(mission_url).status_code, 200)

    def test_source_required_fields(self):
        response = self.client.post(
            "/demande-vehicule", {}, HTTP_ACCEPT="application/json"
        )
        self.assertEqual(response.status_code, 422)
        self.assertTrue(
            {
                "date_visite",
                "effectif_etudiants",
                "destination",
                "duree_visite",
            }.issubset(response.json()["errors"])
        )
        self.assertFalse(DemandeVehicule.objects.exists())

    def test_professor_alias_get_and_post(self):
        self.assertContains(
            self.client.get("/professeur/demande-vehicule"), "Affectation de Véhicule"
        )
        response = self.client.post(
            "/professeur/demande-vehicule",
            json.dumps(self.payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(DemandeVehicule.objects.count(), 1)
        self.assertEqual(self.client.put("/demande-vehicule").status_code, 405)

    def test_source_search_shows_found_card_and_document_links(self):
        result = self.post().json()
        response = self.client.get(
            "/demande-vehicule/suivi", {"code": result["code_suivi"].lower()}
        )
        self.assertEqual(response.status_code, 200)
        for text in [
            "Dossier trouvé",
            "Voir le suivi complet",
            result["code_suivi"],
            "En cours de traitement",
            result["pdf_download_url"],
        ]:
            self.assertContains(response, text)
        self.assertNotContains(response, result["status_url"] + "/ordre-mission-pdf")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(self.client.post("/demande-vehicule/suivi").status_code, 405)

    def test_status_badges_match_source_model(self):
        result = self.post().json()
        obj = DemandeVehicule.objects.get()
        for status, color in [
            ("Validée", "emerald"),
            ("Approuvée", "emerald"),
            ("En cours de traitement", "amber"),
            ("Rejetée", "rose"),
            ("Refusée", "rose"),
            ("Autre", "blue"),
        ]:
            obj.statut = status
            obj.save()
            self.assertEqual(
                obj.status_badge, f"bg-{color}-100 text-{color}-800 border-{color}-300"
            )
            self.assertContains(self.client.get(result["status_url"]), obj.status_badge)

    def test_source_general_tracking_integration(self):
        obj = DemandeVehicule.objects.create(
            code_suivi="ESTFBS-VEH-2026-SRCH1",
            enseignant=self.teacher,
            nom_professeur="Pr. Nohaila HANDAOUI",
            date_visite=self.depart,
            effectif_etudiants=45,
            destination="Marrakech - Salon International de l’Innovation",
            duree_visite="2 jours",
        )
        response = self.client.get("/suivi.php", {"code": obj.code_suivi})
        for text in [obj.code_suivi, "Demande de véhicule", "En cours de traitement"]:
            self.assertContains(response, text)

    def test_document_templates_preserve_source_sections_and_escape_values(self):
        from .vehicle_documents import document_tree

        self.post(
            nom_professeur="Pr. Fatima LAASSIRI",
            destination="Rabat <script>alert(1)</script>",
            motif_visite="Visite <img src='https://example.org/x'> & recherche",
            grade_professeur="PH",
        )
        obj = DemandeVehicule.objects.get()
        request = document_tree(obj, "pdf").find("page-demande")
        for text in [
            "DEMANDE D'AFFECTATION DE VÉHICULE",
            "1. Renseignements",
            "2. Détails de la Visite",
            "3. Effectifs",
            "4. Visas",
            "L'Enseignant Demandeur",
            "Avis Chef de Département",
            "Direction EST-FBS",
        ]:
            self.assertIn(text, request.text())
        self.assertEqual(len(request.all("img")), 2)
        obj.statut = "Validée"
        obj.save()
        mission = document_tree(obj, "ordre-mission-pdf").find("page-container")
        self.assertEqual(len(mission.all("img")), 1)
        self.assertIn("<script>alert(1)</script>", mission.text())
        self.assertIn(self.teacher.grade, mission.text())
        self.assertNotIn("Pr. Pr.", request.text())


class ExistingVehicleMigrationTests(TransactionTestCase):
    def test_existing_vehicle_is_preserved(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        old_target = [("portal", "0003_etudiants_contact_apogee")]
        executor.migrate(old_target)
        old = executor.loader.project_state(old_target).apps.get_model(
            "portal", "DemandeVehicule"
        )
        obj = old.objects.create(
            nom_professeur="Ancien enseignant",
            date_visite=timezone.localdate(),
            effectif_etudiants=20,
            destination="Ancienne destination",
            duree_visite="2 jours",
        )
        try:
            MigrationExecutor(connection).migrate(latest)
            current = DemandeVehicule.objects.get(pk=obj.pk)
            self.assertEqual(current.nom_professeur, "Ancien enseignant")
            self.assertEqual(current.grade_professeur, "")
            self.assertIsNone(current.date_retour)
            self.assertEqual(
                current.date_retour_prevue, current.date_visite + timedelta(days=1)
            )
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())

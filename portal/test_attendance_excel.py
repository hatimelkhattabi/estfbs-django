import hashlib
import io
import json
from pathlib import Path
from django.test import TestCase, override_settings
from pypdf import PdfReader
from .attendance_excel import attendance_sources, source_students
from .attendance_excel_pdf import excel_presence_pdf
from .test_teachers import teacher

ROOT = Path(__file__).resolve().parent / "assets/presence"


@override_settings(
    ATTENDANCE_SOURCE_ROOT=ROOT,
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class AttendanceExcelTests(TestCase):
    def setUp(self):
        self.teacher = teacher()
        self.client.force_login(self.teacher.utilisateur)

    def source(self, year="1", course="Génie Informatique"):
        return next(
            s for s in attendance_sources() if s.filiere == course and s.niveau == year
        )

    def params(self, s):
        return {
            field: getattr(s, field)
            for field in ["filiere", "niveau", "annee_universitaire"]
        }

    def test_nine_original_workbooks_are_unmodified_and_all_27_sheets_are_indexed(self):
        manifest = json.loads((ROOT / "sources.json").read_text())
        self.assertEqual(len(manifest), 9)
        for record in manifest:
            self.assertEqual(
                hashlib.sha256((ROOT / record["file"]).read_bytes()).hexdigest(),
                record["sha256"],
            )
        self.assertEqual(len(attendance_sources()), 27)
        keys = [
            (s.filiere, s.niveau, s.annee_universitaire) for s in attendance_sources()
        ]
        self.assertEqual(len(keys), len(set(keys)))

    def test_preview_uses_excel_without_importing_or_requiring_student_database(self):
        source = self.source()
        response = self.client.get(
            "/espace-enseignant/listes-presence/", self.params(source)
        )
        self.assertContains(response, "82 étudiant(s)")
        self.assertContains(response, source_students(source)[0].nom)
        self.assertContains(response, "fichiers Excel")
        self.assertNotContains(response, "base étudiants est encore vide")
        from .models import Etudiant

        self.assertEqual(Etudiant.objects.count(), 0)

    def test_third_year_preserves_every_name_even_without_apogee(self):
        source = self.source(
            "3",
            "DBT Infrastructures, Traitement et Analyse de données Massives (BIG DATA)",
        )
        students = source_students(source)
        self.assertEqual(len(students), 50)
        self.assertTrue(all(not s.apogee for s in students))
        response = self.client.get(
            "/espace-enseignant/listes-presence/", self.params(source)
        )
        self.assertContains(response, "50 étudiant(s)")
        params = self.params(source) | {"format": "pdf"}
        response = self.client.get("/espace-enseignant/listes-presence/", params)
        self.assertEqual(response["Content-Type"], "application/pdf")
        text = " ".join(
            p.extract_text() for p in PdfReader(io.BytesIO(response.content)).pages
        )
        self.assertIn(students[0].nom, text)
        self.assertIn(students[-1].nom, text)

    def test_dbt_selects_third_year_without_year_or_with_a_conflicting_year(self):
        source = self.source(
            "3",
            "DBT Infrastructures, Traitement et Analyse de données Massives (BIG DATA)",
        )
        params = self.params(source)
        params.pop("niveau")
        for year in [None, "", "1", "2", "invalid"]:
            with self.subTest(year=year):
                response = self.client.get(
                    "/espace-enseignant/listes-presence/",
                    params if year is None else params | {"niveau": year},
                )
                self.assertContains(response, "50 étudiant(s)")
                self.assertContains(response, 'value="3" selected')
                self.assertContains(response, "niveau=3")
                self.assertContains(response, source_students(source)[0].nom)

    def test_dbt_pdf_uses_third_year_even_when_url_requests_first_year(self):
        source = self.source(
            "3",
            "DBT Infrastructures, Traitement et Analyse de données Massives (BIG DATA)",
        )
        response = self.client.get(
            "/espace-enseignant/listes-presence/",
            self.params(source) | {"niveau": "1", "format": "pdf"},
        )
        self.assertEqual(response["Content-Type"], "application/pdf")
        text = " ".join(
            p.extract_text() for p in PdfReader(io.BytesIO(response.content)).pages
        )
        self.assertIn(source_students(source)[-1].nom, text)

    def test_pdf_is_selected_excel_sheet_with_logos_sessions_landscape_and_private_headers(
        self,
    ):
        source = self.source()
        response = self.client.get(
            "/espace-enseignant/listes-presence/",
            self.params(source) | {"format": "pdf"},
        )
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["Referrer-Policy"], "no-referrer")
        reader = PdfReader(io.BytesIO(response.content))
        text = " ".join(p.extract_text() for p in reader.pages)
        self.assertIn("Génie Informatique", text)
        self.assertNotIn("Informatique décisionnelle et statistiques", text)
        self.assertIn(self.teacher.nom_complet, text)
        for page in reader.pages:
            self.assertGreater(float(page.mediabox.width), float(page.mediabox.height))
            self.assertIn("Séance10", page.extract_text())
        self.assertGreaterEqual(len(list(reader.pages[0].images)), 2)

    def test_unknown_class_or_missing_sheet_never_downloads_another_cohort(self):
        params = self.params(self.source()) | {"format": "pdf", "niveau": "3"}
        response = self.client.get("/espace-enseignant/listes-presence/", params)
        self.assertTrue(response["Content-Type"].startswith("text/html"))
        self.assertContains(response, "Aucune feuille Excel")
        params["filiere"] = "../../PRIVATE"
        response = self.client.get("/espace-enseignant/listes-presence/", params)
        self.assertTrue(response["Content-Type"].startswith("text/html"))

    def test_sources_are_not_public_and_pdf_requires_teacher_session(self):
        self.assertEqual(
            self.client.get("/static/presence/2026-2027_DIM_1.xlsx").status_code, 404
        )
        self.client.logout()
        self.assertEqual(
            self.client.get(
                "/espace-enseignant/listes-presence/",
                self.params(self.source()) | {"format": "pdf"},
            ).status_code,
            302,
        )

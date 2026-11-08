"""Install the teacher portal update into an existing EST-FBS Django project.

Only files listed in the adjacent manifest are copied. No database commands run.
"""

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_child(root, relative):
    rel = PurePosixPath(relative)
    if rel.is_absolute() or not rel.parts or any(
        part in {"", ".", ".."} or ":" in part or "\\" in part for part in rel.parts
    ):
        raise ValueError("Chemin interdit dans le manifeste.")
    path = root.joinpath(*rel.parts)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Un chemin sort du dossier du projet : " + relative)
    if path.is_symlink():
        raise ValueError("Lien symbolique refusé : " + relative)
    return path


def atomic_copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".enseignant-", dir=destination.parent)
    os.close(fd)
    temp = Path(name)
    try:
        shutil.copy2(source, temp)
        os.replace(temp, destination)
    finally:
        temp.unlink(missing_ok=True)


def project_python(project):
    options = [project / ".venv/Scripts/python.exe", project / ".venv/bin/python"]
    for candidate in options:
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def check_project(project):
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    # A settings module inherited from a different shell must not select another app.
    env["DJANGO_SETTINGS_MODULE"] = "estfbs.settings"
    python = project_python(project)
    subprocess.run(
        [python, "-X", "utf8", "manage.py", "check"],
        cwd=project,
        env=env,
        check=True,
    )
    verification = (
        "from pathlib import Path; import inspect; "
        "from django.urls import reverse; "
        "from portal import teacher_views; "
        "from portal.models import Enseignant, DemandeImpression, MessageAnonyme, DocumentImpression; from portal.teacher_forms import PrintDocumentForm, AttendanceForm; "
        "root=Path.cwd().resolve(); "
        "assert Path(inspect.getfile(teacher_views)).resolve().is_relative_to(root); "
        "assert reverse('teacher-home') == '/espace-enseignant/'; "
        "assert reverse('teacher-admin-accounts').startswith('/admin/'); "
        "assert (root/'templates/enseignants/home.html').is_file(); "
        "assert (root/'portal/migrations/0005_espace_enseignant.py').is_file(); "
        "assert DocumentImpression._meta.get_field('date_souhaitee'); assert 'date_souhaitee' in PrintDocumentForm.base_fields; assert 'intitule' not in AttendanceForm.base_fields; assert 'date_seance' not in AttendanceForm.base_fields; assert [s for s,label in DemandeImpression.STATUTS] == ['En attente','Vue','Terminée']; assert (root/'portal/migrations/0007_impression_document_dates_status.py').is_file(); assert reverse('teacher-print-edit', args=['00000000-0000-0000-0000-000000000000']).endswith('/modifier/'); assert reverse('teacher-print-delete', args=['00000000-0000-0000-0000-000000000000']).endswith('/supprimer/'); from portal.forms import ContactForm; assert ContactForm.base_fields['email'].required; assert AttendanceForm({'filiere':'DBT Vérification','niveau':'1'}).data['niveau']=='3'; assert (root/'portal/migrations/0008_contact_apogee_only.py').is_file(); from portal.teacher_forms import PrintBatchForm; assert set(PrintBatchForm.base_fields)=={'remarque'}; assert {'type_travail','feuilles_reponse','papier_brouillon'}.issubset(PrintDocumentForm.base_fields); assert (root/'portal/migrations/0009_impression_options_par_document.py').is_file(); print('Contact email/Apogée et options propres à chaque document contrôlés.')"
    )
    subprocess.run(
        [python, "-X", "utf8", "manage.py", "shell", "-c", verification],
        cwd=project,
        env=env,
        check=True,
    )


def install(package, project, dry_run=False, checker=check_project):
    package, project = package.resolve(), project.resolve()
    if package == project:
        raise ValueError("Extrais la mise à jour dans un dossier séparé du projet.")
    if not (project / "manage.py").is_file() or not (
        project / "estfbs/settings.py"
    ).is_file():
        raise ValueError("Le dossier cible doit contenir manage.py et estfbs/settings.py.")
    manifest = json.loads((package / "MANIFEST-ESPACE-ENSEIGNANT.json").read_text("utf-8"))
    if manifest.get("format") != 1 or not isinstance(manifest.get("files"), list):
        raise ValueError("Manifeste de mise à jour invalide.")
    protected = {".env", ".django-local-key", "db.sqlite3", "manage.py"}
    forbidden_roots = {".venv", "private_media", "sauvegardes", "data", ".git"}
    records, seen = [], set()
    for item in manifest["files"]:
        rel = item["path"]
        if rel in seen:
            raise ValueError("Fichier répété dans le manifeste : " + rel)
        seen.add(rel)
        path_parts = PurePosixPath(rel).parts
        if (
            rel in protected
            or not path_parts
            or path_parts[0] in forbidden_roots
            or rel.lower().endswith((".sqlite3", ".sql", ".env"))
        ):
            raise ValueError("Fichier privé ou base de données interdit : " + rel)
        source, target = safe_child(package, rel), safe_child(project, rel)
        if not source.is_file() or digest(source) != item["sha256"]:
            raise ValueError("Fichier absent ou modifié dans la mise à jour : " + rel)
        if target.exists() and not target.is_file():
            raise ValueError("La cible n’est pas un fichier : " + rel)
        records.append((rel, source, target))
    if not records:
        raise ValueError("Le paquet ne contient aucun fichier.")
    print(f"{len(records)} fichiers vérifiés. Projet : {project}")
    if dry_run:
        print("Simulation terminée : aucun fichier modifié.")
        return None

    backup_rel = "sauvegardes/espace-enseignant-" + datetime.now().strftime(
        "%Y%m%d-%H%M%S-%f"
    )
    backup = safe_child(project, backup_rel)
    backup.mkdir(parents=True, exist_ok=False)
    states = []
    # Complete all backups before changing the first project file.
    for rel, _, target in records:
        existed = target.exists()
        states.append({"path": rel, "existed": existed})
        if existed:
            copy = safe_child(backup, rel)
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, copy)
    (backup / "fichiers.json").write_text(
        json.dumps(states, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    touched = []
    try:
        for record, state in zip(records, states):
            rel, source, target = record
            touched.append((rel, target, state["existed"]))
            atomic_copy(source, target)
        checker(project)
    except BaseException:
        failures = []
        for rel, target, existed in reversed(touched):
            try:
                if existed:
                    atomic_copy(safe_child(backup, rel), target)
                else:
                    target.unlink(missing_ok=True)
            except OSError:
                failures.append(rel)
        if failures:
            print("Restauration partielle. Utilise la sauvegarde : " + str(backup))
            print("Fichiers à restaurer : " + ", ".join(failures))
        else:
            print("Contrôle échoué : les fichiers précédents ont été restaurés.")
        raise
    print("Fichiers installés et contrôlés.")
    print("Sauvegarde des fichiers précédents : " + str(backup))
    print("La base n’a pas été modifiée. Depuis le dossier du projet, lance :")
    if os.name == "nt":
        print(r".\.venv\Scripts\python.exe -X utf8 manage.py migrate")
        print(r".\.venv\Scripts\python.exe -X utf8 manage.py runserver 8002")
    else:
        print(".venv/bin/python -X utf8 manage.py migrate")
        print(".venv/bin/python -X utf8 manage.py runserver 8002")
    print("Espace enseignants : http://127.0.0.1:8002/espace-enseignant/")
    return backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        install(Path(__file__).resolve().parent, args.project, args.dry_run)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print("Installation interrompue : " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Demande de véhicule — ordre de mission après validation

Cette mise à jour conserve le formulaire et les PDF repris de ton archive. Elle réserve l’ordre de mission aux demandes ayant le statut **Validée** ou **Approuvée**, enregistré dans l’administration.

## Installation

1. Arrête le serveur avec **Ctrl+C** et garde une copie du projet.
2. Décompresse **EST-FBS-Demande-Vehicule.zip**.
3. Copie son contenu dans **est-fbs-django**, à côté de `manage.py`. Fusionne les dossiers et remplace les fichiers.
4. Depuis ce dossier, exécute dans PowerShell :

```powershell
.\.venv\Scripts\python.exe -X utf8 manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

Ouvre [le formulaire](http://127.0.0.1:8000/demande-vehicule) et actualise avec **Ctrl+F5** pour charger le nouveau JavaScript.

Le ZIP contient aussi les migrations des mises à jour précédentes, au cas où elles n’auraient pas encore été installées. Les migrations déjà appliquées sont conservées. Aucune nouvelle dépendance Python n’est nécessaire.

## Fonctionnement

1. L’enseignant remplit le formulaire et envoie sa demande.
2. Une confirmation avec sa référence et son lien de suivi apparaît. **Aucun téléchargement ne se lance automatiquement.**
3. Avant validation, il peut télécharger uniquement la copie de sa demande. Le PDF ne contient pas l’ordre de mission. Les liens de l’ordre sont masqués dans le suivi ; une ouverture directe de leur URL est également bloquée côté serveur.
4. Dans [l’administration](http://127.0.0.1:8000/admin/?tab=vehicules), ouvre **Demandes de véhicule**.
5. Sur la ligne concernée, choisis **Validée** ou **Approuvée**, puis clique sur **Enregistrer**.
6. L’enseignant actualise son suivi : les boutons **Ordre de mission** et **Demande + Ordre** deviennent disponibles.

Une demande « En cours de traitement », « Rejetée » ou « Refusée » ne donne jamais accès à l’ordre. Si tu retires une validation, ses anciens liens sont de nouveau bloqués et le PDF de demande ne contient plus l’ordre.

Le contrôle s’applique aussi aux administrateurs : enregistre d’abord le statut validé pour pouvoir ouvrir l’ordre.

Les personnes autorisées à modifier les demandes de véhicule dans l’administration peuvent effectuer cette validation. Le formulaire public ne permet pas de choisir ni de modifier son propre statut.

## Adresses conservées

| Méthode | Adresse | Fonction |
| --- | --- | --- |
| GET / POST | `/demande-vehicule` | Formulaire et enregistrement |
| GET / POST | `/professeur/demande-vehicule` | Même formulaire et enregistrement |
| GET | `/demande-vehicule/suivi` | Recherche par référence |
| POST | `/demande-vehicule/ordre-mission-pdf` | Ancienne adresse : enregistre une demande en attente, sans générer d’ordre |
| GET | `/demande-vehicule/{code}` | Statut et récapitulatif |
| GET | `/demande-vehicule/{code}/pdf` | Demande seule avant validation, demande et ordre après validation |
| GET | `/demande-vehicule/{code}/ordre-mission-pdf` | Ordre seul, après validation ; accès refusé sinon |
| GET | `/suivi.php?code={code}` | Suivi général |

La table existante `portal_demandevehicule` et ses anciennes demandes sont conservées. Les demandes déjà marquées « Validée » ou « Approuvée » donnent accès à leur ordre.

## Vérification rapide

Crée une demande test, conserve sa référence et vérifie qu’aucun fichier ne se télécharge à l’envoi. Le PDF de demande doit contenir uniquement la demande. Valide-la dans l’administration et actualise son suivi : l’ordre doit maintenant être accessible et le document combiné doit le contenir.

94 tests passent sur SQLite. Ils couvrent les liens directs, le PDF combiné, les statuts refusés, la validation et son retrait, les permissions administrateur, le formulaire et les autres modules du site. La soumission JavaScript a aussi été vérifiée sans téléchargement automatique. Les PDF avant et après validation ont été rendus et contrôlés.

La migration sur ton instance PostgreSQL et le rendu complet dans ton navigateur restent à vérifier à l’installation.

Le ZIP ne contient ni base de données, ni paramètres de connexion, ni liste d’étudiants.

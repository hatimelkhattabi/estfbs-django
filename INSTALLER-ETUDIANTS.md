# Activer la vérification du numéro Apogée

Cette mise à jour ajoute la liste des étudiants et le contrôle du numéro Apogée dans le formulaire « Contactez l’Administration ».

## 1. Copier la mise à jour

Arrête le serveur avec **Ctrl+C**. Garde une copie de ton projet avant de fusionner les fichiers.

Décompresse `EST-FBS-Verification-Apogee.zip`. Copie son contenu dans le dossier qui contient **manage.py**, en fusionnant les dossiers et en acceptant le remplacement des fichiers.

Le ZIP de mise à jour contient uniquement le code et ce guide. Ton fichier `.env`, ta base, tes documents et tes images ne sont pas inclus.

## 2. Placer le classeur Excel

Place `Etudiants_EST_FBS_2026-2027.xlsx` à côté de `manage.py`.

Le classeur est celui qui a été fusionné à partir des 9 fichiers et 27 feuilles. La commande lit uniquement sa feuille **Etudiants**.

## 3. Ouvrir PowerShell dans le projet

```powershell
cd "C:\Users\hatim\Documents\django\est-fbs-django"
```

Installe la dépendance pour lire Excel :

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-etudiants.txt
```

Ajoute la table des étudiants et les champs des messages :

```powershell
.\.venv\Scripts\python.exe -X utf8 manage.py migrate
```

Les anciens messages sont conservés. Le moteur configuré dans ton `.env`, notamment PostgreSQL, reste celui utilisé.

## 4. Vérifier et importer

Vérifie d’abord le classeur sans modifier la base :

```powershell
.\.venv\Scripts\python.exe -X utf8 manage.py import_etudiants ".\Etudiants_EST_FBS_2026-2027.xlsx" --dry-run
```

Avec le classeur fourni, le résultat attendu est **795 numéros Apogée distincts** et **880 lignes sans Apogée ignorées**.

Effectue ensuite l’import :

```powershell
.\.venv\Scripts\python.exe -X utf8 manage.py import_etudiants ".\Etudiants_EST_FBS_2026-2027.xlsx"
```

Tu peux relancer cette commande après avoir complété les Apogées manquants. Un numéro déjà importé avec les mêmes nom et prénom ne crée pas une deuxième fiche. Les noms identiques avec des numéros différents restent séparés.

Les fiches déjà présentes gardent leurs informations et leur autorisation actuelle. Un même Apogée associé à des noms différents arrête l’import entier sans enregistrer de modification. Corrige alors le classeur ou la fiche depuis l’administration.

## 5. Démarrer et tester

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Ouvre [l’administration des étudiants](http://127.0.0.1:8000/admin/etudiants). Le nouveau menu **Étudiants (Apogée)** permet de rechercher, ajouter, modifier et désactiver une fiche. Un compte qui n’est pas super administrateur doit recevoir les permissions correspondantes.

Sur [la page d’accueil](http://127.0.0.1:8000/), actualise avec **Ctrl+F5**, puis essaie le formulaire de contact :

- Un Apogée importé et autorisé permet l’envoi avec une adresse email valide, un nom, un objet et un message valides.
- Un Apogée absent, vide ou désactivé bloque l’envoi, y compris un envoi direct à l’API.
- Les messages reçus affichent le numéro Apogée dans **Scolarité & messages**.
- Les 880 lignes sans numéro ne peuvent pas encore servir à la vérification. Complète les numéros dans Excel, puis relance l’import.

Le contrôle vérifie l’existence du numéro Apogée. Il ne vérifie pas encore que la personne possède l’adresse email ni que cette adresse correspond au numéro saisi. Le nom n’est pas utilisé pour accepter ou refuser le message.

## Validation effectuée

Les 66 tests du projet ont réussi sur SQLite. L’import du classeur réel a été vérifié : 795 fiches créées, 880 lignes sans numéro ignorées, puis aucune fiche supplémentaire lors d’un second import. Le test sur ton serveur PostgreSQL se fait avec les commandes ci-dessus.

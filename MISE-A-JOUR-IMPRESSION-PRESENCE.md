# Mise à jour impressions et listes de présence

## Installer sur le projet Windows existant

1. Arrête le serveur avec `Ctrl+C` et conserve une sauvegarde PostgreSQL ainsi que `private_media`.
2. Extrais le ZIP `EST-FBS-Impression-Presence-MAJ.zip`, puis copie **son contenu** dans `C:\Users\hatim\Documents\django\est-fbs-django`. Accepte la fusion des dossiers et le remplacement des fichiers. `portal/teacher_forms.py` doit arriver directement dans le dossier `portal` du projet, sans dossier intermédiaire.
3. Depuis PowerShell :

```powershell
cd "C:\Users\hatim\Documents\django\est-fbs-django"
.\.venv\Scripts\python.exe -X utf8 manage.py check
.\.venv\Scripts\python.exe -X utf8 manage.py migrate
.\.venv\Scripts\python.exe -X utf8 manage.py runserver 8002
```

4. Ouvre <http://127.0.0.1:8002/espace-enseignant/> et utilise `Ctrl+F5`.

Le ZIP ne contient ni `.env`, ni base de données, ni documents déposés. La migration à appliquer est `portal.0007_impression_document_dates_status`. Les dépendances Python restent les mêmes.

## Impression

- Le tableau partagé de la colonne droite est retiré ; cet espace reste vide.
- Chaque bloc Document possède sa **date souhaitée** : par exemple, Document 1 pour le 20/11 et Document 2 pour le 25/11. Les exemplaires, faces et formats restent indépendants. Les impressions restent en noir et blanc.
- Les dates sont visibles par document dans le suivi de l’enseignant et dans le panneau d’administration.
- Dans **Administration → Demandes d’impression → Consulter**, choisis **En attente**, **Vue** ou **Terminée**, ajoute une réponse si nécessaire, puis clique sur **Enregistrer le suivi**. Consulter la fiche ne change pas automatiquement son statut. Le statut concerne la demande entière.
- Pour un examen, les feuilles de réponse et le papier brouillon restent des quantités globales. Ils sont à préparer pour la première date demandée parmi les documents ; cette échéance est indiquée dans le formulaire et le suivi.

Les anciennes demandes conservent leurs fichiers, noms et quantités. Leurs documents reçoivent la date de la demande d’origine. Les anciennes intégrations conservent une date sur la demande, égale à la première échéance pour les nouvelles demandes. Les anciennes soumissions à date commune restent reconnues.

Les anciens statuts **Acceptée** et **En cours** deviennent **Vue** ; **Prête à récupérer** devient **Terminée**. Une ancienne demande **Refusée** passe à **Vue**, avec la mention de son ancien refus conservée dans la réponse administrative. Elle n’est pas marquée comme imprimée. Les réponses existantes restent conservées.

## Listes de présence

Les seuls choix sont **Filière**, **Année** (1re, 2e ou 3e année) et **Année universitaire**. Les champs Module ou séance et Date de séance sont retirés du formulaire. Les PDF utilisent désormais la grille des Excel fournis, avec leurs cases de séance à compléter.

Les variantes importées telles que « 1ère année », « 1re année » et « Année 1 » sont regroupées sous le choix 1re année. Une valeur comme « 11e année » n’est pas assimilée à la 1re année. Les filières et années universitaires restent issues de la base Apogée.

Les affectations département → filières → enseignants restent à définir avec la liste que tu transmettras. Cette version conserve donc les filières actuellement disponibles, sans inventer d’affectation. Les classeurs étudiants fournis sont désormais intégrés au ZIP pour la génération privée des listes de présence, sans réimport automatique dans la base.

## Vérifications

176 tests Django passent sur SQLite, notamment les droits de modification des statuts, les dates indépendantes, les fichiers privés, le PDF de présence et la migration d’anciennes demandes depuis 0005 jusqu’à 0007. Les interactions d’ajout/retrait de documents et la conservation de dates distinctes sont vérifiées dans un DOM. Le rendu des pages et du PDF est contrôlé avec un moteur statique ; un contrôle dans ton navigateur reste à faire après installation.

La base PostgreSQL de ton PC n’est pas accessible depuis cet environnement. Exécute bien `manage.py migrate` sur ton projet avant de réouvrir le portail. Les règles existantes de validation administrative de l’ordre de mission restent conservées.

Dernière mise à jour : modification/suppression des impressions en attente, accès au suivi depuis le tableau admin et listes PDF utilisant les 27 feuilles des neuf classeurs fournis. Voir `MISE-A-JOUR-ACTIONS-EXCEL.md` pour le fonctionnement actuel.

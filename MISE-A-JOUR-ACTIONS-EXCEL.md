# Impressions modifiables et listes de présence Excel

## Installation Windows

1. Arrête le serveur avec `Ctrl+C`.
2. Copie le **contenu** de `EST-FBS-Impressions-Modifier-Supprimer-Excel.zip` dans `C:\Users\hatim\Documents\django\est-fbs-django`, puis accepte la fusion des dossiers et le remplacement des fichiers. Évite de créer un sous-dossier supplémentaire portant le nom du ZIP.
3. Depuis PowerShell dans ton projet :

```powershell
.\.venv\Scripts\python.exe -X utf8 manage.py check
.\.venv\Scripts\python.exe -X utf8 manage.py migrate
.\.venv\Scripts\python.exe -X utf8 manage.py runserver 8002
```

Cette modification n’ajoute aucune migration après 0007. La commande `migrate` applique simplement les mises à jour précédentes si elles manquent. Aucune dépendance Python supplémentaire n’est nécessaire. La configuration `.env`, PostgreSQL et les documents déjà déposés restent en place.

## Où se trouvent les suivis ?

- **Administration** : <http://127.0.0.1:8002/admin/impressions/>. Un accès **Impressions enseignants** est ajouté dans le bandeau du tableau d’administration, selon les permissions du compte. Clique sur **Consulter**, choisis **En attente**, **Vue** ou **Terminée**, puis enregistre.
- **Enseignant** : <http://127.0.0.1:8002/espace-enseignant/mes-demandes/>. Les liens **Consulter**, **Modifier** et **Supprimer** apparaissent pour les impressions en attente.

L’administration possède aussi un accès **Documents enseignants** pour les attestations et autres documents administratifs. L’onglet historique Personnel & Professeurs conserve ses anciennes demandes.

## Modifier une demande d’impression

Le propriétaire peut modifier une demande dont le statut est **En attente**. Les fichiers existants sont affichés et peuvent être conservés sans les renvoyer. Il peut remplacer un PDF, retirer une pièce, en ajouter une, modifier les dates, les exemplaires, les faces, le format, les fournitures d’examen et les consignes.

Les dates restent propres à chaque document. Les limites restent de dix documents, 20 Mo par nouveau PDF et 50 Mo au total, y compris les PDF conservés. Une nouvelle date doit être aujourd’hui ou dans le futur.

À partir de **Vue** ou **Terminée**, les modifications et suppressions sont bloquées côté enseignant. Il doit contacter le service d’impression pour une correction. Si une demande change entre l’ouverture et l’enregistrement, le formulaire demande de recharger la version actuelle afin d’éviter d’écraser la modification précédente.

## Supprimer une demande

Le lien **Supprimer** ouvre une page de confirmation. La consultation de cette page ne supprime rien. Le bouton **Oui, supprimer cette demande** retire ensuite la demande et ses pièces ; les PDF qui ne sont plus utilisés sont nettoyés après validation de l’opération. Un fichier encore lié à une autre demande est conservé.

Les actions sont réservées au propriétaire connecté. La protection CSRF reste active.

## Listes de présence provenant des Excel fournis

Les neuf classeurs fournis sont inclus, inchangés, dans `portal/assets/presence`. Ce dossier est privé au projet ; les fichiers ne sont pas placés dans `static`. Leur empreinte et leur nom d’origine figurent dans `sources.json`.

Le portail reconnaît leurs **27 feuilles**. Les choix Filière, Année (1re, 2e, 3e) et Année universitaire correspondent désormais à ces feuilles. L’aperçu et le bouton **Télécharger la liste PDF** utilisent la feuille choisie, sans demander de réimporter les étudiants dans PostgreSQL.

Le PDF reprend les noms, prénoms, Apogée renseignés, l’ordre des lignes, les logos et la grille de dix séances. Les lignes sans Apogée restent présentes. L’en-tête Enseignant reçoit le nom du compte connecté ; la grille d’origine conserve ses cases de séance à compléter sur papier. Le PDF utilise le format A4 paysage, avec les en-têtes répétés sur les pages suivantes.

Les champs Module et Date de séance restent absents du formulaire du site. Les classeurs d’origine ne sont pas modifiés lors d’un téléchargement. Les PDF sont générés à partir de leur feuille ; ce téléchargement ne renvoie pas le classeur entier contenant d’autres filières.

Les affectations département/filières/enseignants restent à configurer avec la liste que tu transmettras. Si aucune feuille ne correspond à une combinaison, aucun document d’une autre classe n’est téléchargé. La table `portal_etudiant`, utilisée notamment pour la vérification Apogée du contact étudiant, n’est pas écrasée par cette fonctionnalité. En l’absence de classeurs dans ce dossier, le fonctionnement précédent à partir de la base reste disponible.

## Vérifications

176 tests Django passent sur SQLite : dates distinctes, trois statuts, droits d’accès, confirmations, CSRF, formulaires périmés, remplacement et nettoyage des fichiers, rollback, limites de taille, maintien des anciennes demandes et lecture des Excel. Les 27 PDF sont générés et contrôlés en conservant les noms et prénoms des feuilles sources. Les interactions des formulaires sont vérifiées dans un DOM et les pages/PDF sont rendus pour inspection visuelle.

Le navigateur Windows et le serveur PostgreSQL de ton PC ne sont pas accessibles ici. Après installation, ouvre le portail sur le bon port et utilise `Ctrl+F5`. Le lien d’ordre de mission reste réservé aux demandes de véhicule validées.

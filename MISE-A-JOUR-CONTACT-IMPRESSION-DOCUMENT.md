# Contact avec email et impression réglée par document

Mise à jour du 8 novembre 2026. Ce guide complète les versions précédentes.

## Contact

Le formulaire comporte, dans cet ordre : email sur toute la largeur, nom et
prénom à côté du numéro Apogée, objet, puis message. Sur un petit écran, les
champs s’affichent les uns sous les autres.

Une adresse email valide est obligatoire, personnelle ou universitaire.
L’Apogée doit correspondre à un étudiant actif. L’email est enregistré avec le
message et figure dans la notification administrative. Les anciens messages
sans email restent conservés.

## Impression

Chaque document possède ses propres réglages :

- Examen ou Autre document.
- Date souhaitée et fichier PDF.
- Exemplaires, recto ou recto verso, format A4 ou A3.
- Pour un examen : feuilles de réponse et papier brouillon, avec leurs quantités.

Exemple : Document 1 = examen du 20/11, 20 exemplaires et 20 feuilles de réponse ;
Document 2 = support de cours du 25/11, 30 exemplaires, sans fournitures d’examen.
Plusieurs examens peuvent aussi avoir des dates et fournitures différentes.
Les fournitures sont préparées à la date du document auquel elles appartiennent.

Cocher une fourniture propose la quantité d’exemplaires de ce document, puis le
nombre reste modifiable. Pour un Autre document, les fournitures sont masquées
et enregistrées à zéro par le serveur.

L’ajout, le retrait et la modification conservent ces réglages par pièce. Les
PDF existants peuvent être conservés sans les renvoyer. Les demandes en attente
restent modifiables et supprimables par leur propriétaire ; les demandes prises
en charge restent verrouillées.

L’administration et le suivi enseignant présentent les détails par document.
Une demande contenant les deux types indique « Examen et autres documents ».
Les statuts restent En attente, Vue et Terminée.

Limites : dix PDF, 20 Mo par fichier, 50 Mo au total, 5 000 exemplaires par
document et 10 000 feuilles de chaque sorte par examen. Impression en noir et blanc.

## Installation du ZIP

Arrêter le serveur avec Ctrl+C. Fusionner les dossiers `portal`, `templates` et
`static` du ZIP avec ceux du projet en acceptant le remplacement des fichiers.
Si l’extraction crée un sous-dossier, copier son contenu dans le dossier qui
contient `manage.py`.

```powershell
cd "C:\Users\hatim\Documents\django\est-fbs-django"
.\.venv\Scripts\python.exe -X utf8 manage.py check
.\.venv\Scripts\python.exe -X utf8 manage.py migrate
.\.venv\Scripts\python.exe -X utf8 manage.py runserver 8002
```

Ouvrir http://127.0.0.1:8002/ et faire Ctrl+F5.

Pour utiliser l’installateur avec sauvegarde automatique, extraire le ZIP dans
un dossier séparé, puis lancer son `INSTALLER_ESPACE_ENSEIGNANT.py --project`
en indiquant le chemin du projet. Le correcteur autonome
`CORRIGER_SERVICES_ENSEIGNANTS.py` contient le même paquet.

## Reprise des anciennes données

La migration `0009_impression_options_par_document` ajoute les options sur
chaque document. Les anciennes pièces reprennent le type de leur demande.
Les fournitures autrefois globales sont rattachées une seule fois au document
à la date la plus proche, puis au premier identifiant en cas d’égalité. Les
totaux ne sont pas multipliés. Les PDF, dates, comptes et statuts sont conservés.
Une ancienne demande sans pièces reste consultable et modifiable.

Une ancienne page d’impression restée ouverte peut encore envoyer l’ancien
format global : le serveur le convertit selon la même règle. Les nouvelles
fiches utilisent toujours leurs propres options.

## Validation

190 tests Django réussis avec SQLite : contact avec email et Apogée, CSRF,
demandes mixtes, dates et fournitures indépendantes, quantités, droits,
modification, suppression et reprise des anciennes données.

Le JavaScript réel a été testé dans un DOM : ajout/retrait/réutilisation,
identifiants uniques, dates séparées, options par examen, quantités distinctes,
PDF conservés, ordre du contact et email transmis avec le jeton CSRF.
Les formulaires et récapitulatifs ont été inspectés par rendu local.
L’installation et la migration ont été vérifiées sur une copie de la version précédente.

Les tests ont utilisé SQLite. PostgreSQL et un navigateur complet n’étaient pas
disponibles pour ces vérifications locales.

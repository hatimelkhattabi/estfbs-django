# Mise à jour des services enseignants

Cette version reprend le portail PPR existant, avec des textes plus grands, des boutons plus faciles à utiliser et quatre services principaux dans cet ordre :

1. Demande d’impression.
2. Documents administratifs.
3. Listes de présence.
4. Demande de véhicule.

Le message anonyme reste accessible dans le menu et depuis le tableau de bord. Le menu se replie sur téléphone ; le suivi regroupe les impressions, les documents administratifs et les véhicules.

## Installer sur ton projet déjà fonctionnel

1. Arrête le serveur avec `Ctrl+C`. Conserve une sauvegarde du projet, de PostgreSQL et de `private_media`.
2. Extrais le **contenu** de `EST-FBS-Espace-Enseignant.zip` dans :

```text
C:\Users\hatim\Documents\django\est-fbs-django
```

Accepte la fusion des dossiers et le remplacement des fichiers. Le fichier `portal/teacher_services.py` doit se trouver directement dans le dossier `portal` du projet ; évite un sous-dossier supplémentaire portant le nom du ZIP. La configuration `.env`, la base et les fichiers déposés ne sont pas dans ce paquet de mise à jour.

3. Dans PowerShell, depuis le projet :

```powershell
cd "C:\Users\hatim\Documents\django\est-fbs-django"
.\.venv\Scripts\python.exe -X utf8 manage.py check
.\.venv\Scripts\python.exe -X utf8 manage.py migrate
.\.venv\Scripts\python.exe -X utf8 manage.py runserver 8002
```

La migration `portal.0006_services_enseignants` crée les services. La migration `portal.0007_impression_document_dates_status` ajoute la date par document et les trois statuts d’impression. Elle crée les nouvelles tables et rattache les documents des anciennes impressions à la nouvelle structure, en conservant leurs chemins et leurs quantités. Les fichiers physiques ne sont pas déplacés. Les informations de la première pièce restent également conservées sur la demande pour les anciennes adresses de téléchargement.

4. Ouvre <http://127.0.0.1:8002/espace-enseignant/>. Utilise `Ctrl+F5` si le navigateur affiche encore l’ancienne mise en page.

Tes comptes PPR existants continuent de fonctionner. La connexion, le changement du mot de passe initial et le correctif CSRF sont conservés. Le guide `INSTALLER-ESPACE-ENSEIGNANT.md` détaille la création manuelle et l’import Excel des comptes.

## Demandes d’impression

Chaque document propose **Examen**, sélectionné au départ, ou **Autre document**. Renseigne sa date souhaitée ; les consignes restent facultatives. Les champs Module ou objet et Filière sont retirés du formulaire d’impression.

Chaque PDF possède sa propre date et ses propres options : nombre d’exemplaires, recto ou recto verso, A4 ou A3. Les nouvelles demandes sont enregistrées en noir et blanc, sans choix de couleur. Un exemplaire signifie une copie du document complet.

Le bouton **Ajouter un autre document** ajoute une pièce avec ses propres réglages. Le bouton **Retirer ce document** retire la pièce de la demande. La limite est de dix PDF, de 20 Mo chacun et 50 Mo au total. Les documents restent privés et accessibles au propriétaire et aux agents autorisés à traiter les impressions.

En mode **Examen**, deux cases supplémentaires permettent de demander :

- Des feuilles de réponse.
- Du papier brouillon.

Après avoir coché une case, indique le **nombre total de feuilles pour cet examen**, pas un nombre par étudiant. Le formulaire propose d’abord la quantité d’exemplaires de ce document ; tu peux la modifier. Exemple : 40 sujets, 40 feuilles de réponse et 80 feuilles de brouillon. Pour un **Autre document**, ces fournitures d’examen ne sont pas demandées.

Après l’envoi, un récapitulatif présente tous les PDF, leurs quantités et les fournitures. L’administration retrouve les mêmes informations dans **Demandes d’impression** et met à jour le statut ou ses consignes. Le site enregistre la demande ; le service d’impression prépare les documents.

Après une erreur de validation, le navigateur demande de sélectionner à nouveau les fichiers. Les options textuelles restent affichées. Une demande invalide n’enregistre aucune pièce.

## Documents administratifs

L’enseignant peut demander une attestation de travail, une attestation de salaire ou un autre document. Pour « Autre document », il précise lequel. Le nom et le PPR sont repris depuis la session.

Dans l’administration, la rubrique **Documents administratifs** permet de consulter la demande, de répondre, de déposer le PDF préparé et de choisir le statut : **En attente**, **En cours**, **Prête** ou **Refusée**.

Le PDF devient téléchargeable par son propriétaire lorsque le statut est **Prête**. Si aucun PDF n’est joint, la demande prête indique un retrait auprès de l’administration ; utilise la réponse pour préciser le service ou les modalités. La plateforme ne fabrique pas de signature ni d’attestation officielle automatiquement.

Les agents concernés doivent avoir les permissions `portal.view_demandedocumentadministratif` et `portal.change_demandedocumentadministratif`. Le superadministrateur y accède directement. Les permissions d’impression et de véhicule existantes continuent de s’appliquer.

## Listes de présence

La rubrique utilise les neuf classeurs Excel fournis dans `portal/assets/presence`, soit 27 feuilles. Choisis la filière, l’année d’études (1re, 2e ou 3e) et l’année universitaire. Le PDF reprend les étudiants de la feuille, les logos et la grille de dix séances, en A4 paysage. Les étudiants sans Apogée restent présents et l’ordre du fichier est conservé. Le formulaire ne demande plus de module ni de date de séance.

L’aperçu affiche les 50 premières personnes ; le PDF contient la classe complète, dans la limite de 2 000 lignes. Les affectations département/filières/enseignants attendent la correspondance à fournir. Sans classeurs installés, le fonctionnement depuis la base Apogée reste disponible. Voir `MISE-A-JOUR-ACTIONS-EXCEL.md` pour les détails actuels.

## Vérifications

- 176 tests Django réussis sur SQLite, dont les contrôles des dates distinctes, des trois statuts et de la migration des anciennes impressions.
- Vérification des interactions dans un DOM : ajout/retrait/réutilisation des pièces, limite de dix documents, quantités distinctes, fournitures d’examen et champ « Autre document ».
- Contrôle des pages rendues et d’un PDF de présence de 70 personnes sur quatre pages : noms longs, accents, en-têtes, signatures et pagination.
- Contrôle Django et absence de modification de modèle sans migration.

Le rendu a été vérifié avec un moteur statique ; un test complet dans ton navigateur reste à effectuer après installation. La génération et les accès aux documents sont couverts par les tests. PostgreSQL doit recevoir la migration sur ton installation : la base de ton PC n’est pas accessible depuis cet environnement.

L’ordre de mission reste téléchargeable uniquement après validation administrative. Les nouvelles impressions n’ouvrent aucun téléchargement automatique.


Le tableau partagé des demandes est retiré. La colonne droite reste vide. Le suivi des impressions utilise les statuts **En attente**, **Vue**, **Terminée**. Le guide `MISE-A-JOUR-IMPRESSION-PRESENCE.md` détaille les nouvelles dates et la conservation des anciennes demandes.

Dernière mise à jour : modification/suppression des impressions en attente, accès au suivi depuis le tableau admin et listes PDF utilisant les 27 feuilles des neuf classeurs fournis. Voir `MISE-A-JOUR-ACTIONS-EXCEL.md` pour le fonctionnement actuel.

La migration 0009 ajoute les options d’examen par document. Voir `MISE-A-JOUR-CONTACT-IMPRESSION-DOCUMENT.md` pour le fonctionnement actuel.

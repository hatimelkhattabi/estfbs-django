# Affichage public, contact Apogée et services enseignants

Mise à jour du 8 novembre 2026.

## Changements

- Le portrait du directeur est légèrement agrandi sur ordinateur.
- Les pages publiques communes passent à une largeur maximale de 1 120 px ;
  les emplois du temps disposent de 1 240 px. Les marges s’adaptent aux écrans étroits.
- Les cartes d’actualités et d’événements ont des images et des textes légèrement
  plus grands. L’image d’une publication ouverte peut atteindre 560 px de hauteur.
  Les vignettes de galerie et la visionneuse sont également agrandies.
- Le contact présente clairement l’envoi d’un message : email, puis nom et numéro Apogée,
  puis objet et message. Le correctif `MISE-A-JOUR-CONTACT-IMPRESSION-DOCUMENT.md` rétablit l’email.
  Le serveur vérifie toujours que cet Apogée correspond à un étudiant actif.
- Le menu latéral de l’administration défile indépendamment de la page sur
  ordinateur. Tous les liens et la déconnexion restent accessibles à la molette.
- « Mon espace enseignants » remplace l’entrée publique « Demande de véhicule »,
  au bas du menu enseignants, avec une icône de compte. Le lien en double est retiré.
- Chaque document d’impression conserve sa propre date, à la création comme à
  la modification. L’intitulé et l’aide précisent ce fonctionnement.
- Dans les listes de présence, une filière dont le nom commence par DBT choisit
  automatiquement la 3e année. La règle est aussi appliquée par Django, même si
  l’URL mentionne une autre année. En quittant une filière DBT, le choix d’année
  redevient libre et doit être effectué pour la nouvelle filière.
- « Message anonyme » figure dans « Mes services » et parmi les cartes du tableau
  de bord enseignants.

## Installation conseillée

Télécharger le fichier `CORRIGER_SERVICES_ENSEIGNANTS.py` fourni avec cette mise
à jour. Ce fichier contient le même paquet que le ZIP, crée une sauvegarde des
fichiers remplacés et vérifie le projet. Il peut être placé à côté de `manage.py`.

Arrêter le serveur avec Ctrl+C. Dans PowerShell, depuis le dossier du projet :

```powershell
cd "C:\Users\hatim\Documents\django\est-fbs-django"
```

Si le correcteur est dans Téléchargements :

```powershell
.\.venv\Scripts\python.exe -X utf8 "$env:USERPROFILE\Downloads\CORRIGER_SERVICES_ENSEIGNANTS.py" --project .
```

S’il a été placé à côté de `manage.py` :

```powershell
.\.venv\Scripts\python.exe -X utf8 .\CORRIGER_SERVICES_ENSEIGNANTS.py --project .
```

Après le message de réussite, exécuter :

```powershell
.\.venv\Scripts\python.exe -X utf8 manage.py migrate
.\.venv\Scripts\python.exe -X utf8 manage.py runserver 8002
```

Ouvrir http://127.0.0.1:8002/ et recharger avec Ctrl+F5.
L’espace enseignants est disponible sur http://127.0.0.1:8002/espace-enseignant/.

La migration `0008_contact_apogee_only` rend facultatif l’ancien champ email des
messages. Les emails des anciens messages sont conservés. Le correcteur ne lance
aucune migration lui-même et ne copie ni `.env`, ni base de données, ni fichiers
téléversés.

## Installation à partir du ZIP

Extraire `EST-FBS-Affichage-Contact-Enseignants.zip` dans un dossier séparé du
projet. Depuis le dossier du projet, lancer l’interpréteur du projet sur le
fichier `INSTALLER_ESPACE_ENSEIGNANT.py` du dossier extrait avec `--project .`.
Exécuter ensuite les deux commandes `migrate` et `runserver` ci-dessus.
L’installateur refuse volontairement que le dossier source soit le dossier cible.

## Contrôles effectués

- 179 tests Django réussis avec SQLite, dont contact sans email, Apogée inconnu
  ou inactif, CSRF, dates par document, modification et suppression réservées au
  propriétaire, statuts et exports de présence.
- Après les derniers ajustements : tests des services enseignants et de leurs
  migrations réussis.
- Contrôles DOM avec le JavaScript réel : création et modification de deux
  documents à dates différentes, année DBT automatique et retour aux autres
  filières, menu enseignants, contact sans email avec jeton CSRF, galerie.
- Contrôle des largeurs des pages publiques par rendu local.
- Contrôle d’installation sur une copie de la version précédente, avec
  conservation de la configuration et des PDF privés.

Le rendu local sert à vérifier les contenus et dimensions. Le défilement à la
molette et le rendu responsive n’ont pas été essayés dans un navigateur complet
dans cet environnement. PostgreSQL n’était pas disponible pour exécuter les tests
ici ; les tests de base de données utilisent SQLite.

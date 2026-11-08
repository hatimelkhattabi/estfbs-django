# EST-FBS — Projet Django

Dernière mise à jour : [contact avec email et options d’impression par document](MISE-A-JOUR-CONTACT-IMPRESSION-DOCUMENT.md). Exécuter `manage.py migrate` après avoir remplacé les fichiers.

Nouvelles options : [Créateur d’images séparé et suppression programmée](MISE-A-JOUR-OPTIONS-ADMIN.md). Cette mise à jour nécessite `manage.py migrate`.

Présentation des cartes Actualités et Événements : [MISE-A-JOUR-CARTES.md](MISE-A-JOUR-CARTES.md).

Mise à jour des titres, du compteur et des emplois du temps : consultez [MISE-A-JOUR-AFFICHAGE.md](MISE-A-JOUR-AFFICHAGE.md).

Version Django du site EST-FBS fourni, avec ses pages publiques, son habillage, ses ressources et une administration personnalisée en français reprenant l’interface Laravel d’origine.

**Déjà installé ?** Consultez [MISE-A-JOUR-ADMIN.md](MISE-A-JOUR-ADMIN.md) pour appliquer la mise à jour sans réinstaller ni remplacer votre base. Aucun serveur PHP ni Composer n’est nécessaire pour cette version.

**Pour passer à PostgreSQL**, suivez [MIGRATION-POSTGRESQL.md](MIGRATION-POSTGRESQL.md). La migration reprend votre base Django actuelle et vos comptes.

## Démarrer sous Windows

Installez Python **3.12 ou 3.13** depuis https://www.python.org/downloads/windows/ puis extrayez le ZIP. Ouvrez PowerShell dans le dossier **est-fbs-django**, celui qui contient `manage.py`.

Pour un premier essai avec les données incluses :

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_site
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

Si `.env` existe déjà, conservez-le et passez la commande `Copy-Item`. `createsuperuser` vous demande de choisir un identifiant et un mot de passe ; aucun compte par défaut n’est fourni.

- Site : http://127.0.0.1:8000/
- Administration : http://127.0.0.1:8000/admin/

Lors des prochains démarrages, seule cette commande est nécessaire :

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Pour arrêter le serveur : **Ctrl+C**. Le projet utilise SQLite par défaut : inutile de démarrer MySQL pour ce premier essai. L’installation des dépendances et les bibliothèques visuelles chargées par CDN demandent une connexion Internet.

**Pour récupérer directement votre vraie base Laravel, suivez plutôt [MIGRATION.md](MIGRATION.md), avant `seed_site`.** L’import doit idéalement se faire dans une nouvelle base Django vide.

## Ce qui est inclus

| Partie | Fonctionnement |
| --- | --- |
| Accueil | Page d’origine, menus, pied de page commun et actualités issues de la base |
| Présentation | Présentation de l’école, missions, 11 DUT et 5 DBT ; liens `#` lorsqu’une brochure manque |
| Actualités et événements | Liste, recherche, filtres, pagination, détail, brouillon, publication programmée et aperçu administrateur |
| Éditeur des publications | Mise en forme, paragraphes français/arabe, images et PDF insérés, document lié au bouton |
| Couvertures | Créateur Canvas 1600 × 800 d’origine : fond personnel, voile, logo, textes déplaçables et téléchargement PNG |
| Annuaire | Professeurs, fiches et photos gérables dans l’administration |
| Galerie | Images et vidéos MP4/WebM, vignette facultative, filtrage et pagination |
| Emplois du temps | DUT S1–S4, DBT S5–S6, documents annuels et envoi de PDF/images par semestre |
| Textes et règlements | Envoi de fichiers ou lien externe, ordre et visibilité |
| Demandes étudiants/personnel | Enregistrement, code de suivi, consultation du statut et traitement dans l’administration |
| Contact | Messages enregistrés dans l’administration ; notification e-mail facultative |
| Demandes de véhicule | Formulaire, suivi, validation administrative et génération PDF |
| Visites | Compteurs et consultation des statistiques dans l’administration |
| Import Laravel | Import MySQL, SQLite ou JSON et copie des fichiers envoyés ; source conservée |

Le back-office principal reprend les écrans de l’ancienne application Laravel : page de connexion, tableau de bord scolarité/messages, barre latérale, tableaux, formulaires, éditeur visuel et créateur de couvertures. Les traitements, validations, permissions et sessions sont gérés par Django. Les services externes déjà liés, comme l’Espace Étudiant et ELOGHA-SUP, restent des liens vers ces plateformes.

## Données fournies et dernières mises à jour

La base SQLite présente dans l’archive source contient **4 publications, 26 professeurs et 9 médias**. Ces données publiques sont dans `data/initial_data.json` et chargées par `seed_site`. Cette commande ajoute aussi les 16 filières sans leurs derniers emplois du temps et les 7 textes/règlements configurés dans le projet d’origine.

Les dernières lignes de votre base MySQL — notamment des actualités, les documents UUID et leurs emplois du temps — ne figuraient pas toutes dans l’archive. Elles se récupèrent avec la commande documentée dans **MIGRATION.md**. Les fichiers privés disponibles dans le ZIP source sont déjà repris dans `private_media/`. Les documents ne deviennent accessibles au public que lorsqu’ils sont référencés par une publication ou un emploi du temps publié, ou par un règlement visible.

`seed_site` ne remplace pas les tables déjà remplies. Les anciennes demandes nominatives, comptes administrateurs et statistiques ne sont pas chargés dans la base d’essai ; l’import de votre vraie base peut les reprendre. Les comptes Laravel demandent l’option explicite `--admins`.

## Utiliser l’administration

Connectez-vous à `/admin/` après `createsuperuser`.

- **Actualités et événements** : remplir le titre, le résumé et le contenu. Envoyer une couverture ou ouvrir « Créer un visuel avec du texte » puis cliquer sur « Utiliser ce visuel » avant d’enregistrer. Cocher « publié » et choisir une date de publication passée pour l’afficher immédiatement. Une date future programme la publication. Pour un événement, renseigner sa date.
- **Bouton et document** : cocher « afficher le bouton », puis envoyer un PDF/image ou saisir un lien. Le fichier envoyé remplace le lien saisi.
- **Emplois du temps** : choisir DUT ou Bachelor, l’année et la filière. Envoyer les documents S1–S4 pour DUT ou S5–S6 pour Bachelor. Les champs des autres semestres sont conservés pour faciliter l’import mais ne sont pas affichés dans ce cycle.
- **Textes et règlements** : envoyer le document, cocher « publié » et régler l’ordre. Un fichier envoyé prend la priorité sur le lien externe.
- **Galerie** : choisir image ou vidéo et envoyer le fichier correspondant. Formats : JPG, PNG, WebP ; MP4 ou WebM pour la vidéo.
- **Demandes** : ouvrir la demande puis modifier son statut et, lorsque proposé, la remarque administrative. La fiche véhicule offre un lien vers le PDF.

Limites d’envoi : **5 Mo pour une image**, **20 Mo pour un document**, **100 Mo pour une vidéo**, **10 Mo pour le fond du générateur**. Sur un hébergement, il faut aussi adapter la limite du serveur HTTP à ces tailles.

## Tester sur un téléphone du même réseau

Dans `.env`, ajoutez l’adresse IPv4 de votre PC à `ALLOWED_HOSTS`. Exemple à adapter après `ipconfig` :

```ini
ALLOWED_HOSTS=localhost,127.0.0.1,[::1],192.168.1.31
```

Relancez le serveur avec :

```powershell
.\.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
```

Sur le téléphone connecté au même Wi-Fi, ouvrez `http://192.168.1.31:8000`. Autorisez Python sur le **réseau privé** si le pare-feu Windows le demande. Utilisez l’IP réelle de votre PC, pas `127.0.0.1` sur le téléphone. Les anciens liens locaux dans vos contenus peuvent nécessiter d’être remplacés par un chemin tel que `/documents/...`.

## Où modifier le code

| Ancien emplacement / rôle | Nouvel emplacement |
| --- | --- |
| `routes/web.php` | `estfbs/urls.py` |
| Contrôleurs Laravel | `portal/views.py` |
| Modèles Eloquent | `portal/models.py` |
| Migrations | `portal/migrations/` |
| En-tête commun | `templates/partials/header.html` |
| Pied de page commun | `templates/partials/footer.html` |
| Mise en page publique | `templates/layouts/public.html` |
| Accueil | `templates/home.html` |
| Présentation | `templates/pages/presentation.html` |
| Filières et brochures du menu | `data/formations.json` |
| Pages actualités | `templates/publications/` |
| Emplois du temps | `templates/emplois/index.html` |
| Styles, scripts, images | `static/` |
| Fichiers envoyés | `private_media/` |
| Interface de l’administration | `templates/admin/`, `static/css/panel.css` |
| Routes et traitements du panneau | `portal/panel_urls.py`, `portal/panel.py` |
| Formulaires et validation du panneau | `portal/forms.py`, `portal/panel_forms.py`, `portal/panel_covers.py` |
| Paramètres et environnement | `estfbs/settings.py`, `.env` |

Les pages publiques utilisent **Jinja2, intégré à Django**. Leur syntaxe est `{% ... %}` / `{{ ... }}` ; elles n’utilisent plus Blade. L’administration principale utilise également Jinja2, avec les mises en page de l’ancien panneau. Les outils natifs Django restent disponibles pour la gestion avancée des comptes et les vues internes. Quelques adresses se terminent encore par `.php` pour garder les anciens liens : elles sont traitées par des vues Python.

## E-mail et configuration

Par défaut les e-mails sont écrits dans la console du serveur et les messages restent enregistrés dans l’administration. Pour envoyer les notifications de contact, renseignez un destinataire et votre serveur SMTP :

```ini
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
CONTACT_EMAIL=adresse-destinataire@exemple.ma
EMAIL_HOST=smtp.exemple.ma
EMAIL_PORT=587
EMAIL_HOST_USER=votre-compte
EMAIL_HOST_PASSWORD=votre-mot-de-passe
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL=adresse-expediteur@exemple.ma
```

Redémarrez Django après toute modification de `.env`.

## Tests et mise en ligne

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test portal
```

Les vérifications effectuées sont détaillées dans [TESTS.md](TESTS.md). Les 38 tests passent. Le projet a été testé avec SQLite sous Linux et Python 3.12 ; l’import depuis votre serveur MySQL et le rendu sur votre téléphone restent à vérifier avec vos données réelles.

`runserver` convient au développement et au test sur le réseau local. Pour héberger le site, utilisez un serveur WSGI/ASGI, HTTPS, une vraie `SECRET_KEY`, `DEBUG=false`, vos domaines dans `ALLOWED_HOSTS`, et les origines HTTPS dans `CSRF_TRUSTED_ORIGINS`. Collectez les ressources avec `python manage.py collectstatic`. Servez uniquement `static_collected/` comme contenu statique ; **ne rendez pas `private_media/` public**. Sauvegardez la base et `private_media/` ensemble.

Les styles Tailwind, icônes Font Awesome et polices Google reprennent les dépendances CDN du site ; Internet est nécessaire pour leur chargement. L’éditeur Quill du panneau principal est fourni localement dans `static/vendor/quill/` et garde un mode texte de secours. Une version entièrement hors ligne nécessiterait de compiler/héberger ces ressources.

Documentation : [Django 5.2](https://docs.djangoproject.com/en/5.2/), [déploiement](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).


## Espace enseignants (PPR)

La mise à jour ajoute un portail `/espace-enseignant/` avec connexion PPR, CIN initiale puis changement obligatoire du mot de passe. Services : impressions multi-document avec fournitures d’examen, documents administratifs, listes de présence, véhicules et messages anonymes. Consulte `MISE-A-JOUR-SERVICES-ENSEIGNANTS.md` pour les migrations 0006/0007 et les nouvelles fonctions. Le guide `INSTALLER-ESPACE-ENSEIGNANT.md` explique l’installation, la création manuelle du premier compte et l’import Excel ultérieur. Aucun compte enseignant n’est créé automatiquement.

Dernière mise à jour enseignants : type, date et fournitures propres à chaque document. Voir `MISE-A-JOUR-CONTACT-IMPRESSION-DOCUMENT.md`.

Impressions : le propriétaire peut modifier ou supprimer ses demandes en attente. Présence : les listes PDF reprennent les neuf classeurs Excel fournis (27 feuilles), y compris les étudiants sans Apogée. Voir `MISE-A-JOUR-ACTIONS-EXCEL.md`.

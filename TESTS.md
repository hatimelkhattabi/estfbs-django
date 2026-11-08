# Vérifications de la version avec l’ancienne administration

## Résultat

**50 tests automatisés réussis** sur SQLite : les 43 tests existants et 7 tests des nouvelles options et de la migration. `manage.py check` ne signale aucune erreur et `makemigrations --check --dry-run` ne demande aucune migration.

Les 13 fichiers JavaScript, dont Quill fourni localement, passent `node --check`. Un audit des 13 écrans d’administration a contrôlé 29 ressources locales : aucune ressource manquante, aucun formulaire imbriqué ni adresse d’action introuvable.

## Panneau personnalisé

Les tests passent par les véritables vues et formulaires :

- Connexion, échec de connexion, déconnexion par POST et protection contre une redirection vers un autre site.
- Listes et formulaires des cinq modules, vides puis avec les données initiales ; formulaires de modification des données importées.
- Création, modification, aperçu, publication/masquage et suppression d’une publication ; documents et images envoyés avec les noms de champs de l’ancien panneau.
- Restitution des champs et des erreurs après un formulaire invalide.
- Conservation de la composition du créateur de visuels et de ses sources privées ; réutilisation des sources lors d’une modification ; refus des paramètres invalides et ignorance des chemins envoyés par le navigateur.
- Professeurs, photos, vidéos, couvertures, retrait d’image et masquage des fiches.
- Envois des PDF par semestre et conservation des anciens liens lors d’un changement de cycle ; documents de règlements.
- Actions du tableau de bord sur les demandes étudiants, personnel, messages et véhicules ; recherche et refus des statuts invalides.
- Permissions de lecture et d’écriture, CSRF et absence d’accès anonyme aux données administratives.
- Recherche, filtres, pagination et rendu des formats Quill, y compris police, taille et direction arabe.

## Application du ZIP de mise à jour

Le patch a été appliqué sur une extraction réelle du premier ZIP, après création d’un compte et d’une publication. Les empreintes de `db.sqlite3`, `.env`, de la clé de session, d’un fichier privé et d’un fichier témoin de `.venv` sont identiques immédiatement après copie. La connexion avec le compte existant fonctionne et la publication reste présente dans le nouveau panneau.

## Site public et migration

Les tests précédents couvrent également les pages publiques avec en-tête et pied de page communs, les 16 filières, les brouillons et publications futures, les liens sûrs, le nettoyage du contenu enrichi, les documents privés, les fichiers et vidéos avec réponses partielles, les demandes avec codes de suivi, les PDF de véhicule, l’import SQLite/JSON sans modification de la source, la conservation des UUID et la reprise des mots de passe bcrypt Laravel.

La première version avait aussi été installée dans un environnement virtuel neuf à partir de `requirements.txt`, avec migrations, données initiales et création d’un superutilisateur. Le panneau personnalisé n’ajoutait pas de changement de schéma. Le support PostgreSQL ajoute désormais le pilote optionnel décrit dans `requirements-postgresql.txt`.

## Portée de la validation

Les tests ont été exécutés sous Linux avec Python 3.12 et Django 5.2.19. Le HTML, les styles et les scripts de l’ancienne interface sont repris des fichiers fournis. Le rendu interactif du Canvas dans votre navigateur, l’utilisation sous Windows et sur votre téléphone, une vraie lecture vidéo multi-navigateurs, votre connexion MySQL et votre SMTP restent à vérifier avec votre configuration réelle.

Le projet complet et le patch ne contiennent aucune base de test, aucun compte prédéfini, aucun fichier `.env` renseigné ou clé locale de session.

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test portal
```

## PostgreSQL

Le backend PostgreSQL Django se charge avec psycopg 3.3.8 et `manage.py check` passe. Les nouveaux tests exercent la sauvegarde, le transfert des mots de passe, groupes, permissions et UUID/JSON, les gardes de moteur/cible vide/empreinte et le rollback sur erreur de comptage. La logique de chargement est testée sur SQLite avec garde de moteur simulé. Aucun serveur PostgreSQL n’était disponible ici ; le transfert réel doit être vérifié sur le PC cible. Consultez MIGRATION-POSTGRESQL.md.

## Affichage public — 6 novembre 2026

Les 43 tests passent après restauration des tableaux DUT/DBT et déplacement du compteur. Les vérifications HTML et les limites du contrôle visuel sont décrites dans MISE-A-JOUR-AFFICHAGE.md.

## Cartes Actualités et Événements

Les 43 tests passent après mise à jour des cartes. Vérification du rendu HTML des deux types de publication, des liens, dates, lieux et titres échappés. Les fichiers du compteur sont identiques à ceux de la version précédente. Voir MISE-A-JOUR-CARTES.md.

## Options de l’administration

50 tests passent avec créateur séparé et suppression programmée. Les tests de l’ancien créateur vérifient désormais sa page autonome et la conservation des compositions. Les tests des options couvrent le délai, les permissions, l’expiration publique, la suppression sur commande et la migration sans échéance des fiches existantes. Les limites du contrôle PostgreSQL, Canvas et Windows sont décrites dans MISE-A-JOUR-OPTIONS-ADMIN.md.


## Portail enseignants — novembre 2026

176 tests passent sur SQLite avec Django 5.2.19. Les cas supplémentaires sont dans `portal/test_teachers.py` : PPR, empreinte de la CIN, mot de passe obligatoire, comptes désactivés, CSRF, import Excel transactionnel, propriété des demandes, accès aux PDF, messages sans relation utilisateur et permissions du panneau. Les tests véhicule existants utilisent désormais un compte enseignant. PostgreSQL doit être vérifié sur l’instance cible après migration.


Le correctif CSRF du portail ajoute quatre tests : en-têtes compatibles avec les formulaires, connexion et changement du mot de passe en HTTP/HTTPS avec CSRF actif, rejet des origines nulles/étrangères et des jetons absents, validation du référent HTTPS sans en-tête Origin.


## Services enseignants : impressions, documents, présence

`portal/test_teacher_services.py` couvre 20 tests : quantités par pièce, examen et fournitures, suppression de pièce, limites de taille/nombre, rollback des fichiers, permissions, documents préparés disponibles après traitement, sélection exacte des cohortes et PDF multi-page. Les interactions JavaScript ont aussi été vérifiées dans un DOM ; le navigateur réel reste à contrôler après installation.


Le formulaire d’impression n’expose plus Module ou objet, Filière et Couleur. Un test vérifie aussi qu’une soumission forgée conserve le noir et blanc et ne renseigne pas les champs retirés.


`portal/test_teacher_revision.py` ajoute dix cas : dates distinctes dans les deux suivis, dates obligatoires, compatibilité de l’ancienne date commune, suppression du tableau partagé, trois statuts et permissions, sélection par année (1re/2e/3e), suppression du module et de la date, migration réelle de 0005 à 0007 conservant les documents et les anciens refus.

Dernière mise à jour : modification/suppression des impressions en attente, accès au suivi depuis le tableau admin et listes PDF utilisant les 27 feuilles des neuf classeurs fournis. Voir `MISE-A-JOUR-ACTIONS-EXCEL.md` pour le fonctionnement actuel.

# Espace enseignants — EST Fkih Ben Salah

Cette mise à jour ajoute `/espace-enseignant/` et reprend le menu bleu marine de l’administration, avec un repère doré sur la rubrique active. Après connexion, les enseignants et personnels disposent des impressions, des documents administratifs, des listes de présence, des demandes de véhicule et du message anonyme. Le guide `MISE-A-JOUR-SERVICES-ENSEIGNANTS.md` détaille les nouveaux formulaires et les migrations 0006 et 0007.

## Installation sur ton projet Windows existant

1. Arrête le serveur Django avec `Ctrl+C`.
2. Fais une sauvegarde de ta base PostgreSQL dans pgAdmin : clic droit sur la base → **Backup…**. Conserve également `private_media`, qui contient les documents déposés. Le ZIP n’embarque ni ta base ni tes identifiants.
3. Extrais complètement `EST-FBS-Espace-Enseignant.zip` dans un dossier séparé. N’exécute pas le script depuis l’aperçu du ZIP.
4. Ouvre PowerShell dans ce dossier extrait, à l’endroit où se trouve `INSTALLER_ESPACE_ENSEIGNANT.py`, puis lance :

```powershell
& "C:\Users\hatim\Documents\django\est-fbs-django\.venv\Scripts\python.exe" .\INSTALLER_ESPACE_ENSEIGNANT.py --project "C:\Users\hatim\Documents\django\est-fbs-django"
```

Le script vérifie les fichiers du paquet, sauvegarde ceux qu’il remplace dans `sauvegardes`, les copie dans le bon projet et exécute le contrôle Django. Il conserve `.env`, les documents et la base. Si le contrôle échoue, il restaure les fichiers précédents. Il ne lance pas de migration et ne modifie pas les données.

5. Une fois le message **Fichiers installés et contrôlés** affiché, ouvre PowerShell dans ton projet :

```powershell
cd "C:\Users\hatim\Documents\django\est-fbs-django"
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -X utf8 manage.py migrate
.\.venv\Scripts\python.exe -X utf8 manage.py runserver 8002
```

Attends que les migrations `portal.0005_espace_enseignant` , `portal.0006_services_enseignants` et `portal.0007_impression_document_dates_status` soient appliquées, puis ouvre :

- Site : <http://127.0.0.1:8002/>
- Administration : <http://127.0.0.1:8002/admin/>
- Espace enseignants : <http://127.0.0.1:8002/espace-enseignant/>

Le port 8002 permet de distinguer ce lancement d’un ancien serveur resté ouvert sur 8000. Les anciennes adresses de demande de véhicule restent reconnues, avec connexion obligatoire.

Le projet complet actualisé contient aussi cette fonctionnalité. Si tu l’utilises pour une nouvelle installation, suis son README, conserve ta configuration et tes documents, puis exécute les migrations.

## Créer un premier compte sans Excel

Dans le panneau d’administration, ouvre **Espace enseignants → Comptes enseignants (PPR) → Nouveau compte**. Renseigne le PPR, le nom, le prénom et la CIN initiale. L’e-mail, le département et le grade peuvent être complétés ensuite. Le compte doit être actif.

Il n’y a aucun compte de démonstration ni mot de passe prédéfini dans le paquet. Utilise un compte de test que tu crées toi-même. Pour tester la connexion enseignant tout en restant connecté à l’administration, utilise une fenêtre de navigation privée : les deux espaces partagent les sessions Django du même site.

L’enseignant se connecte avec son **PPR** et sa **CIN initiale**, puis doit choisir un mot de passe personnel avant d’accéder aux services. La CIN est transformée en empreinte de mot de passe par Django ; elle n’est pas stockée en clair dans les tables. Le compte enseignant n’obtient aucun droit d’administration.

Pour réinitialiser un compte, ouvre sa fiche et saisis une valeur dans **CIN / mot de passe initial**. La prochaine connexion imposera de nouveau un changement. Laisser ce champ vide conserve le mot de passe actuel. Désactiver un compte bloque également ses sessions existantes lors de la prochaine requête.

## Préparer et importer la liste Excel plus tard

Dans **Comptes enseignants (PPR)**, clique sur **Modèle Excel**. Le classeur vierge est aussi fourni dans `portal/assets/Modele_Enseignants.xlsx`.

Conserve la feuille `Enseignants` et les sept premières colonnes :

| PPR | CIN | Nom | Prénom | Email | Département | Grade |
| --- | --- | --- | --- | --- | --- | --- |

Les colonnes PPR et CIN sont au format texte pour conserver les zéros au début. Ne mets aucun compte dans la colonne d’instructions à droite. Le PPR identifie une personne : deux personnes peuvent avoir le même nom, mais un PPR répété dans le même fichier bloque l’import entier.

Dans **Importer Excel**, commence par la simulation cochée par défaut. Si le résultat est correct, décoche la simulation et importe. Pour les nouveaux PPR, la CIN est obligatoire. Pour un PPR déjà présent, les informations du profil sont actualisées ; le mot de passe et l’état actif/inactif sont conservés. Le fichier est limité à 10 000 comptes et 10 Mo. Conserve les fichiers remplis dans un emplacement privé, car ils contiennent les CIN.

L’import est aussi disponible en ligne de commande :

```powershell
.\.venv\Scripts\python.exe -X utf8 manage.py import_enseignants "C:\chemin\Enseignants.xlsx" --dry-run
.\.venv\Scripts\python.exe -X utf8 manage.py import_enseignants "C:\chemin\Enseignants.xlsx"
```

## Services et suivi

### Message anonyme

L’enseignant indique un objet et un message. La table `portal_messageanonyme` ne contient ni auteur, ni PPR, ni lien vers le compte, ni adresse IP. L’administration reçoit le texte et peut le marquer comme lu ou traité. Aucune réponse personnelle n’est possible dans ce service.

L’anonymat décrit ici les données du message. Les journaux techniques de l’hébergement peuvent conserver des traces de connexion ; cette fonction ne garantit pas l’absence de corrélation par un administrateur serveur.

### Demande de véhicule

Le formulaire existant est conservé. Les nouvelles demandes sont liées au compte connecté. Le nom vient du profil ; l’e-mail, le département et le grade sont également repris lorsqu’ils sont renseignés dans le compte. Un enseignant voit uniquement ses propres demandes et documents.

L’ordre de mission reste bloqué tant que le statut n’est pas **Validée** ou **Approuvée** dans l’administration. Aucun téléchargement ne se lance automatiquement à l’envoi. Le PDF récapitulatif de la demande peut être consulté avant validation, sans ordre de mission.

Les demandes créées avant les comptes PPR restent visibles dans l’administration. Elles ne sont pas attribuées automatiquement à un compte à partir d’un nom. Si nécessaire, un administrateur autorisé peut attribuer le compte à une ancienne demande via la fiche classique du modèle `DemandeVehicule`.

### Demande d’impression

L’enseignant dépose jusqu’à dix PDF de 20 Mo chacun (50 Mo au total), choisit une date souhaitée pour chaque document et règle, pour chaque pièce, de 1 à 5 000 exemplaires, recto ou recto verso, A4 ou A3, en noir et blanc. Le mode Examen ajoute les quantités de feuilles de réponse et de brouillon. Un exemplaire signifie une copie du document complet. Exemple : 20 exemplaires, recto verso, A4, pour le 20/11/2026.

Le fichier est enregistré dans `private_media/impressions` et ne reçoit pas de lien de téléchargement public. Seuls son propriétaire et les administrateurs autorisés peuvent l’ouvrir. En production, ne publie pas directement le dossier `private_media` dans Nginx ou Apache.

L’administration dispose de **Demandes d’impression**, avec les statuts **En attente**, **Vue** et **Terminée**, ainsi qu’une réponse administrative. Le propriétaire retrouve le statut et la réponse dans **Mes demandes**. L’impression physique et la livraison du document ne sont pas automatisées.

## Tables et permissions

La migration ajoute `portal_enseignant`, `portal_demandeimpression` et `portal_messageanonyme`. `portal_enseignant` est reliée au compte Django `auth_user`. Les impressions et nouvelles demandes de véhicule sont liées à un enseignant. Les messages anonymes n’ont aucune relation vers un utilisateur.

Le superadministrateur voit les nouvelles rubriques. Pour un agent avec des droits limités, attribue les permissions `view/add/change_enseignant` pour gérer et importer les comptes, `view/change_demandeimpression` pour traiter les impressions et `view/change_messageanonyme` pour traiter les messages. Les permissions de véhicule existantes restent utilisées.

## Vérifications effectuées

176 tests Django réussis sur SQLite : connexion, changement obligatoire du mot de passe, comptes désactivés, protections CSRF, import Excel, propriété des demandes, fichiers privés, permissions d’administration et ordre de mission après validation. Les nouvelles pages ont été rendues pour vérifier leur contenu et leur disposition ; un contrôle dans ton navigateur reste à faire après installation. La migration PostgreSQL doit être exécutée sur ta propre base avec `manage.py migrate`.

Les fichiers de configuration, les documents déposés et les anciens contenus ne sont pas inclus dans le ZIP de mise à jour. Les fichiers remplacés sont sauvegardés, ce qui permet de comparer les éventuelles modifications locales avant de les réintégrer.


## Correctif CSRF — connexion et origine null

L’ancien en-tête `Referrer-Policy: no-referrer` des pages du portail pouvait faire envoyer `Origin: null` par le navigateur lors de la soumission d’un formulaire. Les pages HTML utilisent maintenant `same-origin`. Les téléchargements conservent `no-referrer`. La protection CSRF reste activée ; aucune origine `null` n’est ajoutée aux origines autorisées.

Pour appliquer uniquement ce correctif à une installation déjà en place, remplace la fonction `private` dans `portal/teacher_access.py` par :

```python
def private(response):
    response["Cache-Control"] = "private, no-store"
    response["Referrer-Policy"] = (
        "same-origin"
        if response.get("Content-Type", "").startswith("text/html")
        else "no-referrer"
    )
    return response
```

Redémarre le serveur, puis ouvre à nouveau `/espace-enseignant/connexion/` depuis la barre d’adresse afin de charger un nouveau formulaire. Ne resoumets pas la requête de l’ancienne page 403. Aucun changement de base, migration, compte ou fichier `.env` n’est nécessaire pour ce correctif.

Les tests ajoutés vérifient les en-têtes des formulaires, la connexion et le changement initial du mot de passe avec CSRF actif en HTTP et HTTPS, le contrôle du référent HTTPS et le rejet des origines nulles ou étrangères ainsi que des jetons absents.

Références techniques : <https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Referrer-Policy#effect_on_the_origin_header> et <https://docs.djangoproject.com/en/5.2/ref/middleware/#referrer-policy>.

Dernière mise à jour : modification/suppression des impressions en attente, accès au suivi depuis le tableau admin et listes PDF utilisant les 27 feuilles des neuf classeurs fournis. Voir `MISE-A-JOUR-ACTIONS-EXCEL.md` pour le fonctionnement actuel.

import secrets
import uuid
from datetime import timedelta
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import F, Q
from django.urls import reverse
from django.utils import timezone
from .validators import validate_apogee, validate_document_link


class PublicationQuerySet(models.QuerySet):
    def published(self):
        now = timezone.now()
        return self.filter(publie=True, date_publication__lte=now).filter(
            Q(date_suppression__isnull=True) | Q(date_suppression__gt=now)
        )

    def expired(self):
        return self.filter(
            suppression_apres_jours__isnull=False, date_suppression__lte=timezone.now()
        )


class Publication(models.Model):
    titre = models.CharField("titre", max_length=255)
    type = models.CharField(
        max_length=20,
        choices=[("Actualité", "Actualité"), ("Événement", "Événement")],
        default="Actualité",
    )
    categorie = models.CharField("catégorie", max_length=80, blank=True)
    resume = models.TextField("résumé", max_length=1500)
    contenu = models.TextField("contenu", blank=True)
    contenu_delta = models.JSONField("document de l’éditeur", blank=True, null=True)
    cover_design = models.JSONField("paramètres du visuel", blank=True, null=True)
    image = models.CharField(max_length=500, blank=True)
    date_evenement = models.DateField("date de l’événement", blank=True, null=True)
    date_creation = models.DateTimeField(default=timezone.now)
    date_publication = models.DateTimeField("date de publication", default=timezone.now)
    modifie_le = models.DateTimeField("modifié le", default=timezone.now)
    lieu = models.CharField(max_length=150, blank=True)
    lien = models.CharField(
        "lien ou document",
        max_length=2000,
        blank=True,
        validators=[validate_document_link],
    )
    afficher_bouton = models.BooleanField("afficher le bouton", default=False)
    texte_bouton = models.CharField(
        "texte du bouton", max_length=100, default="Consulter le document"
    )
    bouton_nouvel_onglet = models.BooleanField(
        "ouvrir dans un nouvel onglet", default=True
    )
    ordre = models.PositiveIntegerField(blank=True, null=True)
    publie = models.BooleanField("publié", default=False)
    suppression_apres_jours = models.PositiveIntegerField(
        "suppression automatique après (jours)",
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(3650)],
        help_text="Facultatif. À partir de la date de publication. Vide : conserver sans limite.",
    )
    date_suppression = models.DateTimeField(
        "suppression prévue le", blank=True, null=True, editable=False, db_index=True
    )
    objects = PublicationQuerySet.as_manager()

    class Meta:
        verbose_name = "publication"
        verbose_name_plural = "actualités et événements"
        ordering = [F("ordre").asc(nulls_last=True), "-date_publication", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(suppression_apres_jours__isnull=True)
                | Q(suppression_apres_jours__gte=1, suppression_apres_jours__lte=3650),
                name="publication_deletion_days_range",
            )
        ]

    def __str__(self):
        return self.titre

    def save(self, *args, **kwargs):
        fields = kwargs.get("update_fields")
        if fields is None or {
            "date_publication",
            "suppression_apres_jours",
        }.intersection(fields):
            self.date_suppression = (
                self.date_publication + timedelta(days=self.suppression_apres_jours)
                if self.suppression_apres_jours and self.date_publication
                else None
            )
            if fields is not None:
                kwargs["update_fields"] = set(fields) | {"date_suppression"}
        super().save(*args, **kwargs)

    @property
    def visible(self):
        now = timezone.now()
        return (
            self.publie
            and self.date_publication <= now
            and (self.date_suppression is None or self.date_suppression > now)
        )

    @property
    def image_url(self):
        from .files import asset_url, is_private

        return (
            reverse("publication-image", args=[self.pk])
            if self.image and is_private(self.image)
            else asset_url(self.image or "assets/img/est.jpg")
        )

    @property
    def content_html(self):
        from .richtext import render_content

        return render_content(self.contenu_delta, self.contenu)

    @property
    def lien_valide(self):
        from .validators import valid_link

        return valid_link(self.lien)


class Professeur(models.Model):
    nom = models.CharField(max_length=120)
    prenom = models.CharField("prénom", max_length=120)
    grade = models.CharField(max_length=120, blank=True)
    departement = models.CharField("département", max_length=150, blank=True)
    specialite = models.CharField("spécialité", max_length=180, blank=True)
    email = models.EmailField(blank=True)
    photo = models.CharField(max_length=500, blank=True)
    biographie = models.TextField(blank=True)
    ordre = models.PositiveIntegerField(default=0)
    publie = models.BooleanField("publié", default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["ordre", "nom", "prenom"]

    def __str__(self):
        return self.nom_complet

    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}".strip()

    @property
    def initiales(self):
        return (self.prenom[:1] + self.nom[:1]).upper()

    @property
    def photo_url(self):
        from .files import asset_url, is_private

        return (
            (
                reverse("professeur-photo", args=[self.pk])
                if is_private(self.photo)
                else asset_url(self.photo)
            )
            if self.photo
            else ""
        )


class Photo(models.Model):
    type = models.CharField(
        max_length=10, choices=[("image", "Image"), ("video", "Vidéo")], default="image"
    )
    titre = models.CharField(max_length=200)
    legende = models.TextField("légende", blank=True)
    categorie = models.CharField("catégorie", max_length=100, blank=True)
    fichier = models.CharField(max_length=500)
    vignette = models.CharField(max_length=500, blank=True)
    ordre = models.PositiveIntegerField(default=0)
    publie = models.BooleanField("publié", default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["ordre", "-id"]
        verbose_name = "média"
        verbose_name_plural = "galerie : images et vidéos"

    def __str__(self):
        return self.titre

    @property
    def fichier_url(self):
        from .files import asset_url, is_private

        return (
            reverse("media-file", args=[self.pk])
            if is_private(self.fichier)
            else asset_url(self.fichier)
        )

    @property
    def vignette_url(self):
        from .files import asset_url, is_private

        return (
            (
                reverse("media-thumbnail", args=[self.pk])
                if is_private(self.vignette)
                else asset_url(self.vignette)
            )
            if self.vignette
            else ""
        )


class EmploiDuTemps(models.Model):
    CYCLES = [("DUT", "DUT"), ("Bachelor", "DBT — Bachelor"), ("Licence", "Licence")]
    filiere = models.CharField("filière", max_length=180)
    niveau = models.CharField(max_length=80, blank=True)
    annee = models.CharField("année universitaire", max_length=9, default="2026-2027")
    cycle = models.CharField(max_length=20, choices=CYCLES, blank=True)
    lien = models.CharField(
        max_length=2000, blank=True, validators=[validate_document_link]
    )
    lien_s1 = models.CharField(
        "semestre 1", max_length=2000, blank=True, validators=[validate_document_link]
    )
    lien_s2 = models.CharField(
        "semestre 2", max_length=2000, blank=True, validators=[validate_document_link]
    )
    lien_s3 = models.CharField(
        "semestre 3", max_length=2000, blank=True, validators=[validate_document_link]
    )
    lien_s4 = models.CharField(
        "semestre 4", max_length=2000, blank=True, validators=[validate_document_link]
    )
    lien_s5 = models.CharField(
        "semestre 5", max_length=2000, blank=True, validators=[validate_document_link]
    )
    lien_s6 = models.CharField(
        "semestre 6", max_length=2000, blank=True, validators=[validate_document_link]
    )
    ordre = models.PositiveIntegerField(default=0)
    publie = models.BooleanField("publié", default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-annee", "ordre", "filiere", "id"]
        verbose_name = "emploi du temps"
        verbose_name_plural = "emplois du temps"

    def __str__(self):
        return f"{self.filiere} — {self.cycle} — {self.annee}"

    @property
    def liens(self):
        if self.cycle == "DUT":
            return [(f"S{i}", getattr(self, f"lien_s{i}")) for i in range(1, 5)]
        if self.cycle == "Bachelor":
            return [("S5", self.lien_s5), ("S6", self.lien_s6)]
        return [("Année universitaire", self.lien)]


class UploadedDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    path = models.CharField(max_length=500)
    original_name = models.CharField("nom du fichier", max_length=255)
    mime = models.CharField(max_length=80)
    size = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        verbose_name = "document envoyé"
        verbose_name_plural = "documents envoyés"

    def __str__(self):
        return self.original_name

    @property
    def url(self):
        return reverse("document", args=[self.pk])


class Reglement(models.Model):
    titre = models.CharField(max_length=255)
    langue = models.CharField(
        max_length=2, choices=[("fr", "Français"), ("ar", "العربية")], default="fr"
    )
    file_path = models.CharField(max_length=500, blank=True)
    original_name = models.CharField(max_length=255, blank=True)
    legacy_url = models.CharField(
        "lien externe", max_length=2000, blank=True, validators=[validate_document_link]
    )
    ordre = models.PositiveIntegerField(default=0)
    publie = models.BooleanField("publié", default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["ordre", "id"]
        verbose_name = "texte ou règlement"
        verbose_name_plural = "textes et règlements"

    def __str__(self):
        return self.titre

    @property
    def document_url(self):
        return (
            reverse("reglement-document", args=[self.pk])
            if self.file_path
            else self.legacy_url
        )


REQUEST_STATUSES = [
    (x, x) for x in ["En attente", "En cours", "Prête", "Livrée", "Rejetée"]
]


def student_code():
    return "ESTFBS-" + secrets.token_hex(12)


def staff_code():
    return "PERS-" + secrets.token_hex(12)


def vehicle_code():
    return (
        "ESTFBS-VEH-"
        + str(timezone.localdate().year)
        + "-"
        + secrets.token_hex(12).upper()
    )


class DemandeEtudiant(models.Model):
    code_suivi = models.CharField(
        max_length=64, unique=True, default=student_code, editable=False
    )
    nom_prenom = models.CharField("nom et prénom", max_length=150)
    cne = models.CharField("CNE", max_length=30)
    cin = models.CharField("CIN", max_length=20)
    filiere = models.CharField("filière", max_length=150)
    type_document = models.CharField(max_length=100)
    email = models.EmailField()
    telephone = models.CharField("téléphone", max_length=30, blank=True)
    statut = models.CharField(
        max_length=40, choices=REQUEST_STATUSES, default="En attente"
    )
    remarque_admin = models.TextField("remarque", blank=True)
    date_demande = models.DateTimeField(default=timezone.now)
    date_mise_a_jour = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-date_demande"]
        verbose_name = "demande étudiant"
        verbose_name_plural = "demandes étudiants"

    def __str__(self):
        return self.code_suivi


class DemandePersonnel(models.Model):
    code_suivi = models.CharField(
        max_length=64, unique=True, default=staff_code, editable=False
    )
    nom_prenom = models.CharField("nom et prénom", max_length=150)
    ppr = models.CharField("PPR", max_length=30)
    fonction = models.CharField(max_length=100)
    type_attestation = models.CharField(max_length=100)
    motif = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    statut = models.CharField(
        max_length=40, choices=REQUEST_STATUSES, default="En attente"
    )
    date_demande = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-date_demande"]
        verbose_name = "demande personnel"
        verbose_name_plural = "demandes du personnel"

    def __str__(self):
        return self.code_suivi


class Etudiant(models.Model):
    apogee = models.CharField(
        "numéro Apogée", max_length=32, unique=True, validators=[validate_apogee]
    )
    nom = models.CharField(max_length=150)
    prenom = models.CharField("prénom", max_length=150)
    filiere = models.TextField("filière(s)", blank=True)
    niveau = models.CharField("niveau(x)", max_length=100, blank=True)
    annee_universitaire = models.CharField(
        "année universitaire", max_length=20, blank=True
    )
    actif = models.BooleanField("autorisé à envoyer un message", default=True)
    cree_le = models.DateTimeField(default=timezone.now, editable=False)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nom", "prenom", "apogee"]
        verbose_name = "étudiant (Apogée)"
        verbose_name_plural = "étudiants (Apogée)"

    def __str__(self):
        return f"{self.apogee} — {self.nom} {self.prenom}"


class MessageContact(models.Model):
    etudiant = models.ForeignKey(
        Etudiant,
        on_delete=models.SET_NULL,
        related_name="messages_contact",
        null=True,
        blank=True,
    )
    apogee = models.CharField(
        "Apogée saisi", max_length=32, blank=True, validators=[validate_apogee]
    )
    nom_complet = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    sujet = models.CharField(max_length=255)
    message = models.TextField()
    statut = models.CharField(
        max_length=30,
        choices=[
            ("Nouveau", "Nouveau"),
            ("En cours", "En cours"),
            ("Traité", "Traité"),
        ],
        default="Nouveau",
    )
    date_envoi = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-date_envoi"]
        verbose_name = "message de contact"
        verbose_name_plural = "messages de contact"

    def __str__(self):
        return self.sujet


class DemandeVehicule(models.Model):
    enseignant = models.ForeignKey(
        "Enseignant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicules",
    )
    code_suivi = models.CharField(
        max_length=64, unique=True, default=vehicle_code, editable=False
    )
    nom_professeur = models.CharField("nom du professeur", max_length=150)
    email_professeur = models.EmailField(blank=True)
    grade_professeur = models.CharField(
        "grade du professeur", max_length=150, blank=True
    )
    telephone_professeur = models.CharField(max_length=50, blank=True)
    departement = models.CharField("département", max_length=120, blank=True)
    date_visite = models.DateField("date de visite")
    date_retour = models.DateField("date de retour", blank=True, null=True)
    heure_depart = models.CharField(max_length=20, default="08:30")
    heure_retour = models.CharField(max_length=20, default="17:30")
    effectif_etudiants = models.PositiveSmallIntegerField("effectif étudiants")
    destination = models.CharField(max_length=255)
    organisme_accueil = models.CharField(
        "organisme d’accueil", max_length=200, blank=True
    )
    duree_visite = models.CharField("durée", max_length=100)
    filiere = models.CharField("filière", max_length=150, blank=True)
    type_vehicule = models.CharField(max_length=100, default="Bus Universitaire")
    motif_visite = models.TextField(blank=True)
    accompagnateurs = models.TextField(blank=True)
    statut = models.CharField(
        max_length=40,
        default="En cours de traitement",
        choices=[
            (x, x)
            for x in [
                "En cours de traitement",
                "Validée",
                "Approuvée",
                "Rejetée",
                "Refusée",
            ]
        ],
    )
    remarque_administration = models.TextField(blank=True)
    date_demande = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-date_demande"]
        verbose_name = "demande de véhicule"
        verbose_name_plural = "demandes de véhicule"

    def __str__(self):
        return self.code_suivi

    @property
    def date_retour_prevue(self):
        from .vehicles import return_date

        return self.date_retour or return_date(self.date_visite, self.duree_visite)

    @property
    def ordre_mission_disponible(self):
        return self.statut in {"Validée", "Approuvée"}

    @property
    def status_badge(self):
        if self.statut in {"Validée", "Approuvée"}:
            return "bg-emerald-100 text-emerald-800 border-emerald-300"
        if self.statut == "En cours de traitement":
            return "bg-amber-100 text-amber-800 border-amber-300"
        if self.statut in {"Rejetée", "Refusée"}:
            return "bg-rose-100 text-rose-800 border-rose-300"
        return "bg-blue-100 text-blue-800 border-blue-300"


class SiteVisitor(models.Model):
    visitor_id = models.CharField(max_length=64, unique=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    consultations_count = models.PositiveIntegerField(default=0)
    last_page = models.CharField(max_length=255, blank=True)
    first_visited_at = models.DateTimeField(default=timezone.now)
    last_visited_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "visiteur"
        verbose_name_plural = "visiteurs"

    def __str__(self):
        return self.visitor_id[:12]


class SiteVisit(models.Model):
    visitor_id = models.CharField(max_length=64, db_index=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    page_url = models.CharField(max_length=255, blank=True)
    visited_date = models.DateField(default=timezone.localdate, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "consultation"
        verbose_name_plural = "consultations"


class Enseignant(models.Model):
    utilisateur = models.OneToOneField(
        "auth.User", on_delete=models.CASCADE, related_name="profil_enseignant"
    )
    ppr = models.CharField("PPR", max_length=32, unique=True)
    nom = models.CharField(max_length=150)
    prenom = models.CharField("prénom", max_length=150, blank=True)
    email = models.EmailField(blank=True)
    departement = models.CharField("département", max_length=120, blank=True)
    grade = models.CharField(max_length=150, blank=True)
    actif = models.BooleanField(default=True)
    changer_mot_de_passe = models.BooleanField(default=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom", "prenom"]
        verbose_name = "compte enseignant"
        verbose_name_plural = "comptes enseignants"

    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}".strip()

    def __str__(self):
        return f"{self.ppr} — {self.nom_complet}"


class DemandeImpression(models.Model):
    type_travail = models.CharField(
        max_length=10,
        choices=[
            ("examen", "Examen"),
            ("autre", "Autres documents"),
            ("mixte", "Examen et autres documents"),
        ],
        default="autre",
    )
    intitule = models.CharField("intitulé / module", max_length=180, blank=True)
    filiere = models.CharField("filière", max_length=180, blank=True)
    feuilles_reponse = models.PositiveIntegerField(
        default=0, validators=[MaxValueValidator(100000)]
    )
    papier_brouillon = models.PositiveIntegerField(
        default=0, validators=[MaxValueValidator(100000)]
    )
    STATUTS = [(s, s) for s in ["En attente", "Vue", "Terminée"]]
    enseignant = models.ForeignKey(
        Enseignant, on_delete=models.PROTECT, related_name="impressions"
    )
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    document = models.CharField(max_length=255)
    nom_document = models.CharField(max_length=240)
    date_souhaitee = models.DateField("date souhaitée")
    exemplaires = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5000)]
    )
    mode = models.CharField(
        max_length=20,
        choices=[("recto", "Recto"), ("recto-verso", "Recto verso")],
        default="recto-verso",
    )
    format_papier = models.CharField(
        max_length=2, choices=[("A4", "A4"), ("A3", "A3")], default="A4"
    )
    couleur = models.CharField(
        max_length=10,
        choices=[("NB", "Noir et blanc"), ("couleur", "Couleur")],
        default="NB",
    )
    remarque = models.TextField(blank=True)
    statut = models.CharField(max_length=30, choices=STATUTS, default="En attente")
    reponse_administration = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-cree_le"]
        verbose_name = "demande d’impression"
        verbose_name_plural = "demandes d’impression"

    def __str__(self):
        return f"{self.enseignant.nom_complet} — {self.exemplaires} exemplaires"

    @property
    def documents_a_imprimer(self):
        return list(self.documents.all()) or [self]


class DocumentImpression(models.Model):
    TYPES = [("examen", "Examen"), ("autre", "Autre document")]
    type_travail = models.CharField(max_length=10, choices=TYPES, default="autre")
    feuilles_reponse = models.PositiveSmallIntegerField(
        default=0, validators=[MaxValueValidator(10000)]
    )
    papier_brouillon = models.PositiveSmallIntegerField(
        default=0, validators=[MaxValueValidator(10000)]
    )
    demande = models.ForeignKey(
        DemandeImpression, on_delete=models.CASCADE, related_name="documents"
    )
    document = models.CharField(max_length=255)
    nom_document = models.CharField(max_length=240)
    date_souhaitee = models.DateField("document prêt pour le")
    exemplaires = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5000)]
    )
    mode = models.CharField(
        max_length=20,
        choices=[("recto", "Recto"), ("recto-verso", "Recto verso")],
        default="recto-verso",
    )
    format_papier = models.CharField(
        max_length=2, choices=[("A4", "A4"), ("A3", "A3")], default="A4"
    )
    couleur = models.CharField(
        max_length=10,
        choices=[("NB", "Noir et blanc"), ("couleur", "Couleur")],
        default="NB",
    )

    class Meta:
        ordering = ["pk"]
        verbose_name = "document à imprimer"

    def __str__(self):
        return self.nom_document


class DemandeDocumentAdministratif(models.Model):
    TYPES = [
        (s, s)
        for s in ["Attestation de travail", "Attestation de salaire", "Autre document"]
    ]
    STATUTS = [(s, s) for s in ["En attente", "En cours", "Prête", "Refusée"]]
    enseignant = models.ForeignKey(
        Enseignant, on_delete=models.PROTECT, related_name="documents_administratifs"
    )
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    type_document = models.CharField(max_length=50, choices=TYPES)
    precision = models.CharField("précisez le document", max_length=180, blank=True)
    motif = models.TextField("motif / précisions", blank=True)
    statut = models.CharField(max_length=20, choices=STATUTS, default="En attente")
    reponse_administration = models.TextField(blank=True)
    document = models.CharField(max_length=255, blank=True)
    nom_document = models.CharField(max_length=240, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-cree_le"]
        verbose_name = "demande de document administratif"
        verbose_name_plural = "documents administratifs enseignants"

    def __str__(self):
        return self.precision or self.type_document

    @property
    def telechargeable(self):
        return self.statut == "Prête" and bool(self.document)


class MessageAnonyme(models.Model):
    sujet = models.CharField(max_length=200)
    message = models.TextField()
    statut = models.CharField(
        max_length=20,
        choices=[(s, s) for s in ["Nouveau", "Lu", "Traité"]],
        default="Nouveau",
    )
    date_envoi = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-date_envoi"]
        verbose_name = "message anonyme"
        verbose_name_plural = "messages anonymes"

    def __str__(self):
        return self.sujet

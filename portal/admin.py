from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from .models import (
    Publication,
    Professeur,
    Photo,
    EmploiDuTemps,
    Reglement,
    UploadedDocument,
    DemandeEtudiant,
    DemandePersonnel,
    MessageContact,
    DemandeVehicule,
    SiteVisitor,
    SiteVisit,
    Etudiant,
    DocumentImpression,
    DemandeDocumentAdministratif,
)
from .forms import PublicationForm, ProfesseurForm, PhotoForm, EmploiForm, ReglementForm

admin.site.site_header = "Administration EST-FBS"
admin.site.site_title = "EST-FBS"
admin.site.index_title = "Gestion du portail"


@admin.action(description="Publier la sélection")
def publier(modeladmin, request, queryset):
    queryset.update(publie=True)


@admin.action(description="Passer la sélection en brouillon")
def masquer(modeladmin, request, queryset):
    queryset.update(publie=False)


@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    form = PublicationForm
    list_display = [
        "titre",
        "type",
        "categorie",
        "date_publication",
        "ordre",
        "publie",
        "apercu",
    ]
    list_filter = ["type", "publie", "categorie"]
    search_fields = ["titre", "resume", "categorie"]
    list_editable = ["ordre", "publie"]
    actions = [publier, masquer]
    readonly_fields = ["apercu", "date_suppression", "createur_images"]
    fieldsets = [
        (
            "Publication",
            {
                "fields": (
                    "titre",
                    "type",
                    "categorie",
                    "resume",
                    "contenu",
                    "contenu_delta",
                )
            },
        ),
        ("Image de couverture", {"fields": ("image_upload", "supprimer_image")}),
        ("Créateur d’images", {"fields": ("createur_images",)}),
        (
            "Bouton et document",
            {
                "fields": (
                    "afficher_bouton",
                    "texte_bouton",
                    "lien",
                    "document_lien",
                    "bouton_nouvel_onglet",
                )
            },
        ),
        (
            "Calendrier et affichage",
            {
                "fields": (
                    "date_publication",
                    "suppression_apres_jours",
                    "date_suppression",
                    "date_evenement",
                    "lieu",
                    "ordre",
                    "publie",
                    "apercu",
                )
            },
        ),
    ]

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if not self.has_delete_permission(request, obj):
            fields.append("suppression_apres_jours")
        return fields

    def createur_images(self, obj):
        from django.urls import reverse

        return format_html(
            '<a href="{}" target="_blank" rel="noopener">Ouvrir le créateur d’images ↗</a>',
            reverse("panel-cover-creator"),
        )

    def apercu(self, obj):
        return (
            format_html(
                '<a href="/publications/{}?preview=1" target="_blank" rel="noopener">Aperçu de la publication ↗</a>',
                obj.pk,
            )
            if obj.pk
            else "Enregistrez la publication pour ouvrir son aperçu."
        )


@admin.register(Professeur)
class ProfesseurAdmin(admin.ModelAdmin):
    form = ProfesseurForm
    list_display = ["nom", "prenom", "grade", "departement", "ordre", "publie"]
    list_editable = ["ordre", "publie"]
    list_filter = ["departement", "publie"]
    search_fields = ["nom", "prenom", "email", "specialite"]
    actions = [publier, masquer]


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    form = PhotoForm
    list_display = ["titre", "type", "categorie", "ordre", "publie"]
    list_editable = ["ordre", "publie"]
    search_fields = ["titre", "legende", "categorie"]
    list_filter = ["type", "publie", "categorie"]
    actions = [publier, masquer]


@admin.register(EmploiDuTemps)
class EmploiAdmin(admin.ModelAdmin):
    form = EmploiForm
    list_display = ["filiere", "cycle", "annee", "niveau", "ordre", "publie"]
    list_editable = ["ordre", "publie"]
    list_filter = ["cycle", "annee", "publie"]
    search_fields = ["filiere", "niveau", "annee"]
    actions = [publier, masquer]

    def get_fieldsets(self, request, obj=None):
        return [
            (
                "Filière et affichage",
                {"fields": ["filiere", "cycle", "annee", "niveau", "ordre", "publie"]},
            ),
            (
                "Documents par semestre",
                {
                    "fields": [
                        x
                        for i in range(1, 7)
                        for x in (f"lien_s{i}", f"fichier_lien_s{i}")
                    ]
                },
            ),
            (
                "Document annuel ou ancien document",
                {"fields": ["lien", "fichier_lien"]},
            ),
        ]


@admin.register(Reglement)
class ReglementAdmin(admin.ModelAdmin):
    form = ReglementForm
    list_display = ["titre", "langue", "ordre", "publie"]
    list_editable = ["ordre", "publie"]
    list_filter = ["langue", "publie"]
    search_fields = ["titre"]
    actions = [publier, masquer]


@admin.register(UploadedDocument)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["original_name", "mime", "size", "created_at", "lien_document"]
    search_fields = ["original_name"]
    readonly_fields = [
        "id",
        "path",
        "original_name",
        "mime",
        "size",
        "created_at",
        "created_by",
        "lien_document",
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def lien_document(self, obj):
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">Consulter ↗</a>', obj.url
        )


@admin.register(DemandeEtudiant)
class StudentAdmin(admin.ModelAdmin):
    list_display = [
        "code_suivi",
        "nom_prenom",
        "cne",
        "type_document",
        "statut",
        "date_demande",
    ]
    list_filter = ["statut", "type_document", "filiere"]
    search_fields = ["nom_prenom", "cne", "code_suivi"]
    readonly_fields = ["code_suivi", "date_demande", "date_mise_a_jour"]

    def save_model(self, request, obj, form, change):
        obj.date_mise_a_jour = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(DemandePersonnel)
class PersonnelAdmin(admin.ModelAdmin):
    list_display = [
        "code_suivi",
        "nom_prenom",
        "ppr",
        "type_attestation",
        "statut",
        "date_demande",
    ]
    list_filter = ["statut", "type_attestation"]
    search_fields = ["nom_prenom", "ppr", "code_suivi"]
    readonly_fields = ["code_suivi", "date_demande"]


@admin.register(MessageContact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ["sujet", "nom_complet", "apogee", "email", "statut", "date_envoi"]
    list_filter = ["statut"]
    search_fields = ["sujet", "nom_complet", "apogee", "email", "message"]
    readonly_fields = ["date_envoi", "apogee", "etudiant"]


@admin.register(Etudiant)
class EtudiantAdmin(admin.ModelAdmin):
    list_display = ["apogee", "nom", "prenom", "filiere", "niveau", "actif"]
    search_fields = ["apogee", "nom", "prenom"]
    list_filter = ["actif", "annee_universitaire"]
    readonly_fields = ["cree_le", "modifie_le"]


@admin.register(DemandeVehicule)
class VehicleAdmin(admin.ModelAdmin):
    list_display = [
        "code_suivi",
        "nom_professeur",
        "destination",
        "date_visite",
        "effectif_etudiants",
        "statut",
        "fiche_pdf",
        "ordre_mission_pdf",
    ]
    list_filter = ["statut", "date_visite"]
    search_fields = ["code_suivi", "nom_professeur", "destination"]
    readonly_fields = [
        "code_suivi",
        "date_demande",
        "created_at",
        "updated_at",
        "fiche_pdf",
        "ordre_mission_pdf",
    ]

    def fiche_pdf(self, obj):
        return (
            format_html(
                '<a href="/demande-vehicule/{}/pdf" target="_blank" rel="noopener">PDF ↗</a>',
                obj.code_suivi,
            )
            if obj.pk
            else ""
        )

    def ordre_mission_pdf(self, obj):
        if obj.pk and not obj.ordre_mission_disponible:
            return "Disponible après validation"
        return (
            format_html(
                '<a href="/demande-vehicule/{}/ordre-mission-pdf" target="_blank" rel="noopener">Ordre de mission PDF ↗</a>',
                obj.code_suivi,
            )
            if obj.pk
            else ""
        )


@admin.register(SiteVisitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = [
        "visitor_id",
        "consultations_count",
        "first_visited_at",
        "last_visited_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SiteVisit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ["page_url", "visited_date", "created_at"]
    list_filter = ["visited_date"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


from .models import Enseignant, DemandeImpression, MessageAnonyme


@admin.register(Enseignant)
class TeacherAccountAdmin(admin.ModelAdmin):
    list_display = ["ppr", "nom", "prenom", "actif", "changer_mot_de_passe"]
    search_fields = ["ppr", "nom", "prenom"]
    readonly_fields = [
        "utilisateur",
        "ppr",
        "nom",
        "prenom",
        "email",
        "departement",
        "grade",
        "actif",
        "changer_mot_de_passe",
        "cree_le",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class PrintDocumentInline(admin.TabularInline):
    model = DocumentImpression
    extra = 0
    can_delete = False
    readonly_fields = [
        "nom_document",
        "type_travail",
        "feuilles_reponse",
        "papier_brouillon",
        "document",
        "date_souhaitee",
        "exemplaires",
        "mode",
        "format_papier",
        "couleur",
    ]
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm("portal.view_demandeimpression")


@admin.register(DemandeImpression)
class PrintRequestAdmin(admin.ModelAdmin):
    inlines = [PrintDocumentInline]
    list_display = [
        "enseignant",
        "date_souhaitee",
        "exemplaires",
        "format_papier",
        "mode",
        "statut",
    ]
    list_filter = ["statut", "date_souhaitee"]
    readonly_fields = [
        "type_travail",
        "intitule",
        "filiere",
        "feuilles_reponse",
        "papier_brouillon",
        "enseignant",
        "reference",
        "document",
        "nom_document",
        "date_souhaitee",
        "exemplaires",
        "mode",
        "format_papier",
        "couleur",
        "remarque",
        "cree_le",
        "modifie_le",
    ]

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        # Preserve teacher edits when an administrator is updating only status.
        obj.save(update_fields=["statut", "reponse_administration", "modifie_le"])


@admin.register(MessageAnonyme)
class AnonymousMessageAdmin(admin.ModelAdmin):
    list_display = ["sujet", "date_envoi", "statut"]
    readonly_fields = ["sujet", "message", "date_envoi"]
    list_filter = ["statut"]

    def has_add_permission(self, request):
        return False


@admin.register(DemandeDocumentAdministratif)
class AdministrativeDocumentAdmin(admin.ModelAdmin):
    list_display = ["enseignant", "type_document", "statut", "cree_le"]
    list_filter = ["statut", "type_document"]
    readonly_fields = [
        "enseignant",
        "reference",
        "type_document",
        "precision",
        "motif",
        "document",
        "nom_document",
        "cree_le",
        "modifie_le",
    ]

    def has_add_permission(self, request):
        return False

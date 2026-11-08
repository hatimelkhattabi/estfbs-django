from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from .models import (
    Publication,
    Professeur,
    Photo,
    EmploiDuTemps,
    Reglement,
    DemandeVehicule,
    DemandeEtudiant,
    DemandePersonnel,
    MessageContact,
    Etudiant,
)
from .files import checked_file, save_upload, save_document
from .richtext import sanitize, delta_document
from .validators import validate_apogee


class RichTextWidget(forms.Textarea):
    def __init__(self, attrs=None):
        super().__init__({"class": "est-rich-editor", "rows": 20, **(attrs or {})})

    class Media:
        css = {
            "all": [
                "https://cdn.jsdelivr.net/npm/quill@2.0.3/dist/quill.snow.css",
                "css/django-admin.css",
            ]
        }
        js = [
            "https://cdn.jsdelivr.net/npm/quill@2.0.3/dist/quill.js",
            "js/django-richtext.js",
        ]


class PublicationForm(forms.ModelForm):
    image_upload = forms.FileField(
        label="Image de couverture (5 Mo maximum)", required=False
    )
    supprimer_image = forms.BooleanField(
        label="Supprimer l’image actuelle", required=False
    )
    document_lien = forms.FileField(
        label="PDF ou image pour le bouton (20 Mo maximum)", required=False
    )
    generer_visuel = forms.BooleanField(
        label="Générer une couverture à partir du fond ci-dessous", required=False
    )
    cover_background = forms.FileField(
        label="Fond de la couverture (10 Mo maximum)", required=False
    )
    cover_logo = forms.FileField(label="Logo de la couverture", required=False)
    cover_title = forms.CharField(
        label="Titre du visuel", max_length=90, required=False
    )
    cover_subtitle = forms.CharField(
        label="Sous-titre du visuel", max_length=100, required=False
    )
    cover_footer = forms.CharField(
        label="Pied du visuel", max_length=100, required=False
    )

    class Meta:
        model = Publication
        exclude = ["image", "cover_design", "date_creation", "modifie_le"]
        widgets = {
            "contenu": RichTextWidget(),
            "contenu_delta": forms.HiddenInput(),
            "resume": forms.Textarea(attrs={"rows": 4}),
        }

    def clean(self):
        d = super().clean()
        days = d.get("suppression_apres_jours")
        published_at = d.get("date_publication")
        if (
            days
            and published_at
            and published_at + timedelta(days=days) <= timezone.now()
        ):
            self.add_error(
                "suppression_apres_jours",
                "La date de suppression serait déjà passée. Augmentez le délai ou modifiez la date de publication.",
            )
        for field, kind, limit in [
            ("image_upload", "image", 5),
            ("document_lien", "document", 20),
            ("cover_background", "image", 10),
            ("cover_logo", "image", 5),
        ]:
            if d.get(field):
                try:
                    checked_file(d[field], kind, limit)
                except ValidationError as e:
                    self.add_error(field, e)
        if d.get("type") == "Événement" and not d.get("date_evenement"):
            self.add_error("date_evenement", "Renseignez la date de l’événement.")
        if (
            d.get("afficher_bouton")
            and not d.get("lien")
            and not d.get("document_lien")
        ):
            self.add_error("lien", "Ajoutez un lien ou un document pour le bouton.")
        if d.get("generer_visuel") and not d.get("cover_background"):
            self.add_error("cover_background", "Choisissez une image de fond.")
        if d.get("contenu_delta") and not delta_document(d["contenu_delta"]):
            self.add_error("contenu_delta", "Le document mis en forme est invalide.")
        d["contenu"] = sanitize(d.get("contenu", ""))
        return d

    def save(self, commit=True):
        obj = super().save(False)
        d = self.cleaned_data
        if d.get("supprimer_image"):
            obj.image = ""
        if d.get("image_upload"):
            obj.image = save_upload(d["image_upload"], "publications", "image")[0]
        if d.get("document_lien"):
            obj.lien = save_document(d["document_lien"]).url
        if d.get("generer_visuel"):
            from .covers import create_cover

            obj.image = create_cover(
                d["cover_background"],
                d.get("cover_logo"),
                d.get("cover_title") or obj.titre,
                d.get("cover_subtitle", ""),
                d.get("cover_footer", ""),
            )
            obj.cover_design = {
                "title": d.get("cover_title", ""),
                "subtitle": d.get("cover_subtitle", ""),
                "footer": d.get("cover_footer", ""),
            }
        obj.modifie_le = timezone.now()
        if commit:
            obj.save()
        return obj


class ProfesseurForm(forms.ModelForm):
    photo_upload = forms.FileField(label="Photo du professeur", required=False)
    supprimer_photo = forms.BooleanField(
        required=False, label="Supprimer la photo actuelle"
    )

    class Meta:
        model = Professeur
        exclude = ["photo", "created_at", "updated_at"]

    def clean_photo_upload(self):
        f = self.cleaned_data.get("photo_upload")
        if f:
            checked_file(f, "image")
        return f

    def save(self, commit=True):
        o = super().save(False)
        if self.cleaned_data.get("supprimer_photo"):
            o.photo = ""
        if self.cleaned_data.get("photo_upload"):
            o.photo = save_upload(
                self.cleaned_data["photo_upload"], "professeurs", "image"
            )[0]
        o.updated_at = timezone.now()
        if commit:
            o.save()
        return o


class PhotoForm(forms.ModelForm):
    fichier_upload = forms.FileField(label="Fichier image ou vidéo", required=False)
    vignette_upload = forms.FileField(label="Vignette de la vidéo", required=False)

    class Meta:
        model = Photo
        exclude = ["fichier", "vignette", "created_at", "updated_at"]

    def clean(self):
        d = super().clean()
        if not self.instance.pk and not d.get("fichier_upload"):
            self.add_error("fichier_upload", "Choisissez le fichier du média.")
        if (
            self.instance.pk
            and d.get("type") != self.instance.type
            and not d.get("fichier_upload")
        ):
            self.add_error(
                "fichier_upload", "Choisissez un fichier correspondant au nouveau type."
            )
        for name, kind in [
            ("fichier_upload", "video" if d.get("type") == "video" else "image"),
            ("vignette_upload", "image"),
        ]:
            if d.get(name):
                try:
                    checked_file(d[name], kind)
                except ValidationError as e:
                    self.add_error(name, e)
        return d

    def save(self, commit=True):
        o = super().save(False)
        for name, target, kind in [
            ("fichier_upload", "fichier", "video" if o.type == "video" else "image"),
            ("vignette_upload", "vignette", "image"),
        ]:
            if self.cleaned_data.get(name):
                setattr(
                    o, target, save_upload(self.cleaned_data[name], "gallery", kind)[0]
                )
        o.updated_at = timezone.now()
        if commit:
            o.save()
        return o


class EmploiForm(forms.ModelForm):
    fichier_lien = forms.FileField(
        label="Envoyer un PDF ou une image — document annuel", required=False
    )
    fichier_lien_s1 = forms.FileField(
        label="Envoyer un PDF ou une image — semestre 1", required=False
    )
    fichier_lien_s2 = forms.FileField(
        label="Envoyer un PDF ou une image — semestre 2", required=False
    )
    fichier_lien_s3 = forms.FileField(
        label="Envoyer un PDF ou une image — semestre 3", required=False
    )
    fichier_lien_s4 = forms.FileField(
        label="Envoyer un PDF ou une image — semestre 4", required=False
    )
    fichier_lien_s5 = forms.FileField(
        label="Envoyer un PDF ou une image — semestre 5", required=False
    )
    fichier_lien_s6 = forms.FileField(
        label="Envoyer un PDF ou une image — semestre 6", required=False
    )

    class Meta:
        model = EmploiDuTemps
        exclude = ["created_at", "updated_at"]

    def clean(self):
        d = super().clean()
        for name, value in list(d.items()):
            if name.startswith("fichier_") and value:
                try:
                    checked_file(value)
                except ValidationError as e:
                    self.add_error(name, e)
        return d

    def save(self, commit=True):
        o = super().save(False)
        for key in ["lien"] + [f"lien_s{i}" for i in range(1, 7)]:
            if self.cleaned_data.get("fichier_" + key):
                setattr(o, key, save_document(self.cleaned_data["fichier_" + key]).url)
        o.updated_at = timezone.now()
        if commit:
            o.save()
        return o


class ReglementForm(forms.ModelForm):
    document = forms.FileField(label="Document PDF ou image", required=False)

    class Meta:
        model = Reglement
        exclude = ["file_path", "original_name", "created_at", "updated_at"]

    def clean_document(self):
        f = self.cleaned_data.get("document")
        if f:
            checked_file(f)
        return f

    def clean(self):
        d = super().clean()
        if (
            not d.get("document")
            and not self.instance.file_path
            and not d.get("legacy_url")
        ):
            raise ValidationError("Envoyez un document ou renseignez un lien externe.")
        return d

    def save(self, commit=True):
        o = super().save(False)
        f = self.cleaned_data.get("document")
        if f:
            o.file_path = save_upload(f, "reglements")[0]
            o.original_name = f.name
        o.updated_at = timezone.now()
        if commit:
            o.save()
        return o


class StudentForm(forms.ModelForm):
    class Meta:
        model = DemandeEtudiant
        fields = [
            "nom_prenom",
            "cne",
            "cin",
            "filiere",
            "type_document",
            "email",
            "telephone",
        ]

    def clean_cne(self):
        return self.cleaned_data["cne"].strip().upper()

    def clean_cin(self):
        return self.cleaned_data["cin"].strip().upper()


class PersonnelForm(forms.ModelForm):
    class Meta:
        model = DemandePersonnel
        fields = ["nom_prenom", "ppr", "fonction", "type_attestation", "motif", "email"]


class ContactForm(forms.ModelForm):
    email = forms.EmailField(
        label="Votre email",
        max_length=254,
        error_messages={"required": "Renseignez votre adresse email."},
    )
    apogee = forms.CharField(
        label="Numéro Apogée",
        max_length=32,
        validators=[validate_apogee],
        error_messages={"required": "Renseignez votre numéro Apogée."},
    )

    class Meta:
        model = MessageContact
        fields = ["email", "nom_complet", "apogee", "sujet", "message"]

    def clean_apogee(self):
        apogee = self.cleaned_data["apogee"]
        self.verified_student = Etudiant.objects.filter(
            apogee=apogee, actif=True
        ).first()
        if self.verified_student is None:
            raise ValidationError(
                "Ce numéro Apogée n’est pas autorisé. Vérifiez votre numéro ou contactez la scolarité.",
                code="unknown_apogee",
            )
        return apogee

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.etudiant = self.verified_student
        if commit:
            obj.save()
        return obj


class EtudiantForm(forms.ModelForm):
    class Meta:
        model = Etudiant
        fields = [
            "apogee",
            "nom",
            "prenom",
            "filiere",
            "niveau",
            "annee_universitaire",
            "actif",
        ]
        widgets = {"filiere": forms.Textarea(attrs={"rows": 3})}


class VehicleForm(forms.ModelForm):
    nom_professeur = forms.CharField(min_length=3, max_length=150)
    destination = forms.CharField(min_length=2, max_length=200)
    type_vehicule = forms.CharField(max_length=100, required=False)
    heure_depart = forms.TimeField(
        required=False, widget=forms.TimeInput(attrs={"type": "time"})
    )
    heure_retour = forms.TimeField(
        required=False, widget=forms.TimeInput(attrs={"type": "time"})
    )
    motif_visite = forms.CharField(max_length=3000, required=False)
    accompagnateurs = forms.CharField(max_length=1000, required=False)

    class Meta:
        model = DemandeVehicule
        fields = [
            "nom_professeur",
            "grade_professeur",
            "email_professeur",
            "telephone_professeur",
            "departement",
            "date_visite",
            "date_retour",
            "heure_depart",
            "heure_retour",
            "effectif_etudiants",
            "destination",
            "organisme_accueil",
            "duree_visite",
            "filiere",
            "type_vehicule",
            "motif_visite",
            "accompagnateurs",
        ]
        widgets = {
            "date_visite": forms.DateInput(attrs={"type": "date"}),
            "heure_depart": forms.TimeInput(attrs={"type": "time"}),
            "heure_retour": forms.TimeInput(attrs={"type": "time"}),
            "motif_visite": forms.Textarea(attrs={"rows": 4}),
            "accompagnateurs": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_date_visite(self):
        d = self.cleaned_data["date_visite"]
        if d < timezone.localdate():
            raise ValidationError(
                "La date de visite ne peut pas être antérieure à aujourd’hui."
            )
        return d

    def clean_effectif_etudiants(self):
        v = self.cleaned_data["effectif_etudiants"]
        if not 1 <= v <= 150:
            raise ValidationError("L’effectif doit être compris entre 1 et 150.")
        return v

    def clean_heure_depart(self):
        value = self.cleaned_data.get("heure_depart")
        return value.strftime("%H:%M") if value else "08:30"

    def clean_heure_retour(self):
        value = self.cleaned_data.get("heure_retour")
        return value.strftime("%H:%M") if value else "17:30"

    def clean(self):
        from .vehicles import return_date, suggested_vehicle

        data = super().clean()
        depart, retour = data.get("date_visite"), data.get("date_retour")
        if depart:
            retour = retour or return_date(depart, data.get("duree_visite"))
            data["date_retour"] = retour
            if retour < depart:
                self.add_error(
                    "date_retour",
                    "La date de retour doit suivre ou égaler la date de départ.",
                )
            elif retour == depart and data.get("heure_retour", "") < data.get(
                "heure_depart", ""
            ):
                self.add_error(
                    "heure_retour",
                    "L’heure de retour doit suivre l’heure de départ pour une visite le même jour.",
                )
        data["grade_professeur"] = data.get("grade_professeur") or "PES"
        data["organisme_accueil"] = data.get("organisme_accueil") or data.get(
            "destination", ""
        )
        if data.get("effectif_etudiants") and not data.get("type_vehicule"):
            data["type_vehicule"] = suggested_vehicle(data["effectif_etudiants"])
        return data

import re
from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from .models import (
    Enseignant,
    DemandeImpression,
    DocumentImpression,
    MessageAnonyme,
    DemandeDocumentAdministratif,
    Etudiant,
)
from .files import checked_file
from .attendance_cohorts import YEAR_CHOICES, year_number


def ppr_value(value):
    value = str(value or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9-]{0,31}", value):
        raise ValidationError(
            "Le PPR doit contenir de 1 à 32 lettres ou chiffres, sans espace."
        )
    return value


def cin_value(value):
    value = str(value or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{4,20}", value):
        raise ValidationError(
            "La CIN initiale doit contenir de 4 à 20 lettres ou chiffres."
        )
    return value


class TeacherLoginForm(forms.Form):
    ppr = forms.CharField(label="Votre PPR", max_length=32, validators=[ppr_value])
    password = forms.CharField(
        label="Mot de passe",
        max_length=256,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def clean_ppr(self):
        return ppr_value(self.cleaned_data["ppr"])


class EnseignantForm(forms.ModelForm):
    cin_initiale = forms.CharField(
        label="CIN / mot de passe initial",
        required=False,
        max_length=20,
        widget=forms.PasswordInput(render_value=False),
        help_text="À la création : CIN obligatoire. À la modification : laisser vide pour conserver le mot de passe. Une nouvelle valeur impose un changement à la prochaine connexion.",
    )

    class Meta:
        model = Enseignant
        fields = ["ppr", "nom", "prenom", "email", "departement", "grade", "actif"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cin_initiale"].required = not self.instance.pk
        if self.instance.pk:
            self.fields["ppr"].disabled = True

    def clean_ppr(self):
        value = ppr_value(self.cleaned_data["ppr"])
        if (
            not self.instance.pk
            and User.objects.filter(username="enseignant_" + value).exists()
        ):
            raise ValidationError(
                "Un compte utilise déjà ce PPR. Contactez l’administrateur."
            )
        return value

    def clean_cin_initiale(self):
        value = self.cleaned_data.get("cin_initiale", "")
        return cin_value(value) if value else ""

    @transaction.atomic
    def save(self, commit=True):
        if not commit:
            raise ValueError("Le compte doit être enregistré avec son utilisateur.")
        obj = super().save(commit=False)
        user = (
            obj.utilisateur
            if obj.pk
            else User(username="enseignant_" + self.cleaned_data["ppr"])
        )
        user.first_name = obj.prenom[:150]
        user.last_name = obj.nom[:150]
        user.email = obj.email
        user.is_active = obj.actif
        if self.cleaned_data.get("cin_initiale"):
            user.set_password(self.cleaned_data["cin_initiale"])
            obj.changer_mot_de_passe = True
        user.save()
        obj.utilisateur = user
        obj.save()
        return obj


class ImpressionForm(forms.ModelForm):
    fichier = forms.FileField(
        label="Document PDF",
        help_text="PDF uniquement, 20 Mo maximum.",
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf,application/pdf"}),
    )

    class Meta:
        model = DemandeImpression
        fields = [
            "date_souhaitee",
            "exemplaires",
            "mode",
            "format_papier",
            "couleur",
            "remarque",
        ]
        widgets = {
            "exemplaires": forms.NumberInput(attrs={"min": 1, "max": 5000}),
            "date_souhaitee": forms.DateInput(
                attrs={"type": "date"}, format="%Y-%m-%d"
            ),
            "remarque": forms.Textarea(attrs={"rows": 4, "maxlength": 2000}),
        }

    def clean_date_souhaitee(self):
        value = self.cleaned_data["date_souhaitee"]
        if value < timezone.localdate():
            raise ValidationError("Choisissez aujourd’hui ou une date future.")
        return value

    def clean_remarque(self):
        value = self.cleaned_data["remarque"]
        if len(value) > 2000:
            raise ValidationError("La remarque est limitée à 2 000 caractères.")
        return value

    def clean_fichier(self):
        upload = self.cleaned_data["fichier"]
        if (
            not upload.name.lower().endswith(".pdf")
            or checked_file(upload, max_mb=20) != "application/pdf"
        ):
            raise ValidationError("Choisissez un document PDF valide.")
        return upload


class AnonymousForm(forms.ModelForm):
    class Meta:
        model = MessageAnonyme
        fields = ["sujet", "message"]
        widgets = {"message": forms.Textarea(attrs={"rows": 8, "maxlength": 5000})}

    def clean_message(self):
        value = self.cleaned_data["message"].strip()
        if not 5 <= len(value) <= 5000:
            raise ValidationError(
                "Le message doit contenir entre 5 et 5 000 caractères."
            )
        return value


class PrintBatchForm(forms.ModelForm):
    class Meta:
        model = DemandeImpression
        fields = ["remarque"]
        labels = {"remarque": "Consignes supplémentaires"}
        widgets = {"remarque": forms.Textarea(attrs={"rows": 3, "maxlength": 2000})}

    def clean_remarque(self):
        value = self.cleaned_data["remarque"]
        if len(value) > 2000:
            raise ValidationError("Les consignes sont limitées à 2 000 caractères.")
        return value


class PrintDocumentForm(ImpressionForm):
    avec_feuilles_reponse = forms.BooleanField(
        label="Feuilles de réponse", required=False
    )
    avec_papier_brouillon = forms.BooleanField(label="Papier brouillon", required=False)
    feuilles_reponse = forms.IntegerField(
        label="Nombre total de feuilles de réponse",
        min_value=1,
        max_value=10000,
        required=False,
    )
    papier_brouillon = forms.IntegerField(
        label="Nombre total de feuilles de brouillon",
        min_value=1,
        max_value=10000,
        required=False,
    )

    class Meta(ImpressionForm.Meta):
        model = DocumentImpression
        fields = [
            "type_travail",
            "date_souhaitee",
            "exemplaires",
            "mode",
            "format_papier",
            "feuilles_reponse",
            "papier_brouillon",
        ]
        labels = {
            "date_souhaitee": "Date souhaitée pour ce document",
            "exemplaires": "Nombre d’exemplaires",
            "mode": "Faces",
            "format_papier": "Format",
        }
        widgets = {
            "type_travail": forms.RadioSelect,
            "exemplaires": forms.NumberInput(attrs={"min": 1, "max": 5000}),
            "date_souhaitee": forms.DateInput(
                attrs={"type": "date"}, format="%Y-%m-%d"
            ),
        }

    def __init__(self, *args, **kwargs):
        kwargs["initial"] = {"type_travail": "examen", **(kwargs.get("initial") or {})}
        super().__init__(*args, **kwargs)
        self.fields["exemplaires"].initial = 1
        self.fields["date_souhaitee"].widget.attrs[
            "min"
        ] = timezone.localdate().isoformat()

    def clean(self):
        data = super().clean()
        for count, checked in [
            ("feuilles_reponse", "avec_feuilles_reponse"),
            ("papier_brouillon", "avec_papier_brouillon"),
        ]:
            if data.get("type_travail") != "examen" or not data.get(checked):
                self._errors.pop(count, None)
                data[count] = 0
            elif not data.get(count):
                self.add_error(count, "Indiquez le nombre total de feuilles souhaité.")
        return data


class PrintDocumentFormSet(forms.BaseFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        uploads = [
            f.cleaned_data.get("fichier")
            for f in self.forms
            if not f.cleaned_data.get("DELETE")
        ]
        if sum(f.size for f in uploads if f) > 50 * 1024 * 1024:
            raise ValidationError(
                "La demande est limitée à 50 Mo au total. Répartissez les documents en plusieurs demandes."
            )


PrintDocuments = forms.formset_factory(
    PrintDocumentForm,
    formset=PrintDocumentFormSet,
    extra=0,
    min_num=1,
    validate_min=True,
    max_num=10,
    validate_max=True,
    absolute_max=12,
    can_delete=True,
)


class AdministrativeDocumentForm(forms.ModelForm):
    class Meta:
        model = DemandeDocumentAdministratif
        fields = ["type_document", "precision", "motif"]
        widgets = {"motif": forms.Textarea(attrs={"rows": 4, "maxlength": 2000})}

    def clean(self):
        data = super().clean()
        if data.get("type_document") == "Autre document":
            if not data.get("precision"):
                self.add_error("precision", "Indiquez le document souhaité.")
        else:
            data["precision"] = ""
        if len(data.get("motif", "")) > 2000:
            self.add_error("motif", "Le motif est limité à 2 000 caractères.")
        return data


def cohort_values(field):
    values = set()
    for raw in (
        Etudiant.objects.filter(actif=True).values_list(field, flat=True).distinct()
    ):
        values.update(v.strip() for v in raw.split(" / ") if v.strip())
    return sorted(values, key=str.casefold)


class AttendanceForm(forms.Form):
    filiere = forms.ChoiceField(label="Filière")
    niveau = forms.ChoiceField(
        label="Année",
        choices=[("", "Choisir…")] + YEAR_CHOICES,
        widget=forms.Select(attrs={"aria-describedby": "attendance-dbt-help"}),
    )
    annee_universitaire = forms.ChoiceField(label="Année universitaire")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        filiere = (
            self.data.get(self.add_prefix("filiere"), "")
            if self.is_bound
            else self.initial.get("filiere", "")
        )
        self.is_dbt = bool(re.match(r"^DBT\b", str(filiere), re.I))
        if not self.is_bound and self.is_dbt:
            self.initial["niveau"] = "3"
        # Keep bookmarked links using former imported labels working.
        if self.is_bound:
            self.data = self.data.copy()
            key = self.add_prefix("niveau")
            # DBT is the third year, including links without an explicit year.
            normalized = "3" if self.is_dbt else year_number(self.data.get(key))
            if normalized:
                self.data[key] = normalized
        from .attendance_excel import attendance_sources

        sources = attendance_sources()
        for field in ["filiere", "annee_universitaire"]:
            values = (
                sorted({getattr(source, field) for source in sources}, key=str.casefold)
                if sources
                else cohort_values(field)
            )
            self.fields[field].choices = [("", "Choisir…")] + [(v, v) for v in values]

from django import forms
from django.http import Http404
from .forms import PublicationForm
from .files import find_file, save_upload
from .panel_covers import clean_design


class ComposedPublicationForm(PublicationForm):
    cover_design = forms.JSONField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["texte_bouton"].required = False

    def clean_cover_design(self):
        value = self.cleaned_data.get("cover_design")
        return clean_design(value) if value else None

    def clean(self):
        data = super().clean()
        design = data.get("cover_design")
        old = self.instance.cover_design or {}
        if data.get("afficher_bouton") and not data.get("texte_bouton"):
            self.add_error("texte_bouton", "Renseignez le texte du bouton.")
        else:
            data["texte_bouton"] = data.get("texte_bouton") or "Consulter le document"
        if design:
            if not data.get("image_upload") or data.get("supprimer_image"):
                self.add_error(
                    "image_upload",
                    "Cliquez sur « Utiliser ce visuel » avant d’enregistrer la publication.",
                )
            for kind, custom in [
                ("background", design["background"] == "custom"),
                (
                    "logo",
                    design["logo"]["source"] == "custom" and design["logo"]["visible"],
                ),
            ]:
                if custom and not data.get("cover_" + kind):
                    path = old.get(kind + "Asset", "")
                    try:
                        if not isinstance(path, str) or not path.startswith(
                            ("uploads/", "covers/", "publications/")
                        ):
                            raise Http404
                        find_file(path)
                    except Http404:
                        self.add_error(
                            "cover_" + kind,
                            "Choisissez à nouveau votre image personnelle.",
                        )
        return data

    def save(self, commit=True):
        old = self.instance.cover_design or {}
        obj = super().save(False)
        data = self.cleaned_data
        design = data.get("cover_design")
        if design:
            for kind, custom in [
                ("background", design["background"] == "custom"),
                ("logo", design["logo"]["source"] == "custom"),
            ]:
                if custom:
                    upload = data.get("cover_" + kind)
                    if upload:
                        design[kind + "Asset"] = save_upload(
                            upload, "covers", "image", 10 if kind == "background" else 5
                        )[0]
                    elif old.get(kind + "Asset"):
                        design[kind + "Asset"] = old[kind + "Asset"]
                    elif kind == "logo":
                        design["logo"]["source"] = "default"
            obj.cover_design = design
        elif data.get("image_upload") or data.get("supprimer_image"):
            obj.cover_design = None
        if commit:
            obj.save()
        return obj

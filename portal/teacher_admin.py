from django import forms
from django.db import transaction
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect
from django.conf import settings
from django.views.decorators.http import require_http_methods, require_GET
from .panel import guarded, panel_page
from .models import (
    Enseignant,
    DemandeImpression,
    MessageAnonyme,
    DemandeDocumentAdministratif,
)
from .teacher_forms import EnseignantForm
from .teacher_import import read_teachers, import_teachers, TeacherImportError


def permission(request, model, action="view"):
    if not request.user.has_perm(f"portal.{action}_{model}"):
        raise PermissionDenied


@guarded
@require_GET
def accounts(request):
    permission(request, "enseignant")
    qs = Enseignant.objects.select_related("utilisateur")
    q = request.GET.get("q", "").strip()[:150]
    if q:
        qs = qs.filter(
            Q(ppr__icontains=q) | Q(nom__icontains=q) | Q(prenom__icontains=q)
        )
    return panel_page(
        request,
        "admin/enseignants/accounts.html",
        section="teacher-accounts",
        page_title="Comptes enseignants (PPR)",
        rows=Paginator(qs, 20).get_page(request.GET.get("page")),
    )


@guarded
@require_http_methods(["GET", "POST"])
def account_edit(request, pk=None):
    permission(request, "enseignant", "change" if pk else "add")
    obj = get_object_or_404(Enseignant, pk=pk) if pk else Enseignant()
    form = EnseignantForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        try:
            form.save()
        except IntegrityError:
            form.add_error(
                None, "Un compte avec ce PPR existe déjà. Rechargez la page."
            )
        else:
            messages.success(request, "Le compte enseignant a été enregistré.")
            return redirect("teacher-admin-accounts")
    return panel_page(
        request,
        "admin/enseignants/account_form.html",
        section="teacher-accounts",
        page_title=(
            "Modifier un compte enseignant" if pk else "Créer un compte enseignant"
        ),
        form=form,
    )


class ImportForm(forms.Form):
    fichier = forms.FileField(
        label="Liste Excel des enseignants",
        help_text="Modèle .xlsx, feuille Enseignants, 10 Mo maximum.",
    )
    simulation = forms.BooleanField(
        label="Vérifier seulement, sans modifier les comptes",
        required=False,
        initial=True,
    )


@guarded
@require_http_methods(["GET", "POST"])
def accounts_import(request):
    permission(request, "enseignant", "add")
    permission(request, "enseignant", "change")
    form = ImportForm(request.POST or None, request.FILES or None)
    result = None
    if request.method == "POST" and form.is_valid():
        try:
            result = import_teachers(
                read_teachers(form.cleaned_data["fichier"]),
                dry_run=form.cleaned_data["simulation"],
            )
        except (TeacherImportError, IntegrityError) as exc:
            form.add_error(
                None,
                (
                    str(exc)
                    if isinstance(exc, TeacherImportError)
                    else "Un PPR existe déjà. Aucun changement enregistré."
                ),
            )
        else:
            if form.cleaned_data["simulation"]:
                messages.success(
                    request,
                    f"Vérification terminée : {result['created']} création(s), {result['updated']} mise(s) à jour. Aucune donnée modifiée.",
                )
            else:
                messages.success(
                    request,
                    f"Import terminé : {result['created']} création(s), {result['updated']} mise(s) à jour. Les mots de passe existants sont conservés.",
                )
                return redirect("teacher-admin-accounts")
    return panel_page(
        request,
        "admin/enseignants/import.html",
        section="teacher-accounts",
        page_title="Importer les comptes enseignants",
        form=form,
    )


@guarded
@require_GET
def account_template(request):
    permission(request, "enseignant", "add")
    path = settings.BASE_DIR / "portal/assets/Modele_Enseignants.xlsx"
    response = FileResponse(
        path.open("rb"),
        as_attachment=True,
        filename=path.name,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Cache-Control"] = "private, no-store"
    return response


class PrintStatusForm(forms.ModelForm):
    class Meta:
        model = DemandeImpression
        fields = ["statut", "reponse_administration"]
        labels = {"reponse_administration": "Réponse / consigne pour l’enseignant"}
        widgets = {
            "reponse_administration": forms.Textarea(
                attrs={"rows": 4, "maxlength": 2000}
            )
        }

    def clean_reponse_administration(self):
        value = self.cleaned_data["reponse_administration"]
        if len(value) > 2000:
            raise forms.ValidationError("La réponse est limitée à 2 000 caractères.")
        return value


@guarded
@require_GET
def prints(request):
    permission(request, "demandeimpression")
    qs = DemandeImpression.objects.select_related("enseignant").prefetch_related(
        "documents"
    )
    status = request.GET.get("statut", "")
    if status in dict(DemandeImpression.STATUTS):
        qs = qs.filter(statut=status)
    return panel_page(
        request,
        "admin/enseignants/prints.html",
        section="teacher-prints",
        page_title="Demandes d’impression",
        rows=Paginator(qs, 20).get_page(request.GET.get("page")),
        statuses=DemandeImpression.STATUTS,
    )


@guarded
@require_http_methods(["GET", "POST"])
@transaction.atomic
def print_edit(request, reference):
    permission(request, "demandeimpression")
    qs = DemandeImpression.objects.select_related("enseignant")
    if request.method == "POST":
        qs = qs.select_for_update()
    obj = get_object_or_404(qs, reference=reference)
    editable = request.user.has_perm("portal.change_demandeimpression")
    form = PrintStatusForm(request.POST or None, instance=obj)
    if request.method == "POST":
        permission(request, "demandeimpression", "change")
        if form.is_valid():
            form.save(commit=False).save(
                update_fields=["statut", "reponse_administration", "modifie_le"]
            )
            messages.success(request, "Le suivi d’impression a été mis à jour.")
            return redirect("teacher-admin-print-detail", reference=reference)
    return panel_page(
        request,
        "admin/enseignants/print_form.html",
        section="teacher-prints",
        page_title="Gérer une impression",
        item=obj,
        form=form,
        editable=editable,
    )


class MessageStatusForm(forms.ModelForm):
    class Meta:
        model = MessageAnonyme
        fields = ["statut"]


@guarded
@require_GET
def anonymous_messages(request):
    permission(request, "messageanonyme")
    return panel_page(
        request,
        "admin/enseignants/messages.html",
        section="teacher-messages",
        page_title="Messages anonymes",
        rows=Paginator(MessageAnonyme.objects.all(), 20).get_page(
            request.GET.get("page")
        ),
    )


@guarded
@require_http_methods(["GET", "POST"])
def message_edit(request, pk):
    permission(request, "messageanonyme")
    obj = get_object_or_404(MessageAnonyme, pk=pk)
    editable = request.user.has_perm("portal.change_messageanonyme")
    form = MessageStatusForm(request.POST or None, instance=obj)
    if request.method == "POST":
        permission(request, "messageanonyme", "change")
        if form.is_valid():
            form.save()
            messages.success(request, "Le message a été mis à jour.")
            return redirect("teacher-admin-message-detail", pk=pk)
    return panel_page(
        request,
        "admin/enseignants/message_form.html",
        section="teacher-messages",
        page_title="Message anonyme",
        item=obj,
        form=form,
        editable=editable,
    )


from .files import checked_file, save_upload, private_storage
from .teacher_views import original_filename


class AdministrativeStatusForm(forms.ModelForm):
    fichier = forms.FileField(
        label="Document préparé (PDF)",
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf,application/pdf"}),
        help_text="Facultatif : sans PDF, le document sera à retirer auprès de l’administration.",
    )

    class Meta:
        model = DemandeDocumentAdministratif
        fields = ["statut", "reponse_administration"]
        widgets = {
            "reponse_administration": forms.Textarea(
                attrs={"rows": 4, "maxlength": 2000}
            )
        }

    def clean_fichier(self):
        upload = self.cleaned_data.get("fichier")
        if upload and (
            not upload.name.lower().endswith(".pdf")
            or checked_file(upload, max_mb=20) != "application/pdf"
        ):
            raise forms.ValidationError("Choisissez un PDF valide de 20 Mo maximum.")
        return upload

    def clean_reponse_administration(self):
        value = self.cleaned_data["reponse_administration"]
        if len(value) > 2000:
            raise forms.ValidationError("La réponse est limitée à 2 000 caractères.")
        return value


@guarded
@require_GET
def administrative_documents(request):
    permission(request, "demandedocumentadministratif")
    qs = DemandeDocumentAdministratif.objects.select_related("enseignant")
    status = request.GET.get("statut", "")
    if status in dict(DemandeDocumentAdministratif.STATUTS):
        qs = qs.filter(statut=status)
    return panel_page(
        request,
        "admin/enseignants/documents.html",
        section="teacher-documents",
        page_title="Documents administratifs enseignants",
        rows=Paginator(qs, 20).get_page(request.GET.get("page")),
        statuses=DemandeDocumentAdministratif.STATUTS,
    )


@guarded
@require_http_methods(["GET", "POST"])
def administrative_document_edit(request, reference):
    permission(request, "demandedocumentadministratif")
    obj = get_object_or_404(
        DemandeDocumentAdministratif.objects.select_related("enseignant"),
        reference=reference,
    )
    editable = request.user.has_perm("portal.change_demandedocumentadministratif")
    form = AdministrativeStatusForm(
        request.POST or None, request.FILES or None, instance=obj
    )
    if request.method == "POST":
        permission(request, "demandedocumentadministratif", "change")
        if form.is_valid():
            path = None
            try:
                item = form.save(commit=False)
                upload = form.cleaned_data.get("fichier")
                if upload:
                    path, _ = save_upload(upload, "administratifs", max_mb=20)
                    item.document, item.nom_document = path, original_filename(upload)
                item.save()
            except Exception:
                if path:
                    private_storage().delete(path)
                raise
            messages.success(request, "La demande de document a été mise à jour.")
            return redirect("teacher-admin-document-detail", reference=reference)
    return panel_page(
        request,
        "admin/enseignants/document_form.html",
        section="teacher-documents",
        page_title="Préparer un document administratif",
        item=obj,
        form=form,
        editable=editable,
    )

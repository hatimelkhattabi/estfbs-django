"""Owner-only changes to print requests that have not yet been taken in charge."""

import logging
from django import forms
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_http_methods
from .models import DemandeImpression, DocumentImpression
from .teacher_access import teacher_required
from .teacher_forms import PrintBatchForm, PrintDocumentForm, PrintDocumentFormSet
from .teacher_views import page, original_filename
from .files import private_storage, save_upload
from .printing_options import PRINT_OPTIONS, legacy_print_data, print_summary

logger = logging.getLogger(__name__)


class PrintEditForm(PrintBatchForm):
    revision = forms.CharField(widget=forms.HiddenInput, max_length=60)


class PrintDeleteForm(forms.Form):
    revision = forms.CharField(widget=forms.HiddenInput, max_length=60)


class EditDocumentForm(PrintDocumentForm):
    document_id = forms.CharField(
        required=False, max_length=40, widget=forms.HiddenInput
    )

    def __init__(self, *args, existing_documents=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.existing_documents = existing_documents or {}
        token = (
            self.data.get(self.add_prefix("document_id"), "")
            if self.is_bound
            else self.initial.get("document_id", "")
        )
        self.existing_document = self.existing_documents.get(str(token))
        self.fields["fichier"].required = self.existing_document is None
        if self.existing_document:
            self.fields["fichier"].label = "Remplacer le PDF (facultatif)"

    def clean_fichier(self):
        return super().clean_fichier() if self.cleaned_data.get("fichier") else None

    def clean_document_id(self):
        value = self.cleaned_data["document_id"]
        if value and value not in self.existing_documents:
            raise forms.ValidationError("Ce document n’appartient pas à cette demande.")
        return value

    def clean(self):
        data = super().clean()
        if self.existing_document and not data.get("fichier"):
            try:
                self.retained_size = private_storage().size(
                    self.existing_document.document
                )
            except OSError:
                self.add_error(
                    "fichier",
                    "Le PDF actuel est introuvable. Remplacez-le ou retirez ce document.",
                )
        return data


class EditDocumentsFormSet(PrintDocumentFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        active = [f for f in self.forms if not f.cleaned_data.get("DELETE")]
        ids = [
            f.cleaned_data.get("document_id")
            for f in active
            if f.cleaned_data.get("document_id")
        ]
        if len(ids) != len(set(ids)):
            raise forms.ValidationError(
                "Un document existant ne peut figurer qu’une fois."
            )
        total = sum(
            (
                f.cleaned_data["fichier"].size
                if f.cleaned_data.get("fichier")
                else getattr(f, "retained_size", 0)
            )
            for f in active
        )
        if total > 50 * 1024 * 1024:
            raise forms.ValidationError(
                "Les PDF conservés et ajoutés dépassent 50 Mo au total."
            )


EditDocuments = forms.formset_factory(
    EditDocumentForm,
    formset=EditDocumentsFormSet,
    extra=0,
    min_num=1,
    validate_min=True,
    max_num=10,
    validate_max=True,
    absolute_max=12,
    can_delete=True,
)


def owned_request(request, reference, lock=False):
    qs = DemandeImpression.objects.filter(enseignant=request.enseignant)
    if lock:
        qs = qs.select_for_update()
    return get_object_or_404(qs, reference=reference)


def locked_response(request, item):
    response = page(
        request,
        "print_locked.html",
        active="printing",
        item=item,
        page_title="Demande déjà prise en charge",
    )
    response.status_code = 409
    return response


def purge_unused_files(paths, request=None):
    failed = False
    for path in set(paths):
        # Uploads use private UUID paths. Never remove arbitrary legacy assets.
        if not path.startswith("impressions/") or ".." in path.split("/"):
            continue
        try:
            if (
                DemandeImpression.objects.filter(document=path).exists()
                or DocumentImpression.objects.filter(document=path).exists()
            ):
                continue
            private_storage().delete(path)
        except Exception:
            failed = True
            logger.exception("Print file cleanup failed: %s", path)
    if failed and request is not None:
        messages.warning(
            request,
            "La demande est enregistrée, mais le nettoyage d’un ancien PDF doit être repris par l’administration.",
        )


@teacher_required
@require_http_methods(["GET", "POST"])
def edit(request, reference):
    item = owned_request(request, reference)
    if item.statut != "En attente":
        return locked_response(request, item)
    existing = list(item.documents.all())
    entries = {str(d.pk): d for d in existing} if existing else {"legacy": item}
    initial = [
        {
            "document_id": key,
            **{field: getattr(doc, field) for field in PRINT_OPTIONS},
            "avec_feuilles_reponse": bool(doc.feuilles_reponse),
            "avec_papier_brouillon": bool(doc.papier_brouillon),
        }
        for key, doc in entries.items()
    ]
    data = legacy_print_data(request.POST if request.method == "POST" else None)
    form = PrintEditForm(
        data,
        instance=item,
        initial={
            "revision": item.modifie_le.isoformat(),
        },
    )
    documents = EditDocuments(
        data,
        request.FILES if request.method == "POST" else None,
        prefix="documents",
        initial=initial,
        form_kwargs={"existing_documents": entries},
    )
    response_status = 200
    if request.method == "POST":
        valid_form, valid_documents = form.is_valid(), documents.is_valid()
        if valid_form and valid_documents:
            uploaded = []
            try:
                with transaction.atomic():
                    current = owned_request(request, reference, lock=True)
                    if current.statut != "En attente":
                        return locked_response(request, current)
                    if form.cleaned_data["revision"] != current.modifie_le.isoformat():
                        form.add_error(
                            None,
                            "Cette demande a changé depuis son ouverture. Rechargez la page avant de la modifier.",
                        )
                        response_status = 409
                    else:
                        old_paths = {current.document, *(d.document for d in existing)}
                        kept = []
                        for document_form in documents:
                            values = document_form.cleaned_data
                            if not values or values.get("DELETE"):
                                continue
                            original = entries.get(values.get("document_id"))
                            upload = values.get("fichier")
                            if upload:
                                path, _ = save_upload(upload, "impressions", max_mb=20)
                                uploaded.append(path)
                                name = original_filename(upload)
                            else:
                                path, name = original.document, original.nom_document
                            doc = (
                                original
                                if isinstance(original, DocumentImpression)
                                else DocumentImpression(demande=current)
                            )
                            for key in PRINT_OPTIONS:
                                setattr(doc, key, values[key])
                            doc.document, doc.nom_document, doc.couleur = (
                                path,
                                name,
                                "NB",
                            )
                            doc.save()
                            kept.append(doc)
                        current.documents.exclude(pk__in=[d.pk for d in kept]).delete()
                        current.remarque = form.cleaned_data["remarque"]
                        for key, value in print_summary(kept).items():
                            setattr(current, key, value)
                        first = min(kept, key=lambda d: d.pk)
                        for key in (
                            "document",
                            "nom_document",
                            "exemplaires",
                            "mode",
                            "format_papier",
                            "couleur",
                        ):
                            setattr(current, key, getattr(first, key))
                        current.date_souhaitee = min(d.date_souhaitee for d in kept)
                        current.save()
                        transaction.on_commit(
                            lambda: purge_unused_files(old_paths, request), robust=True
                        )
                if not form.errors:
                    messages.success(
                        request, "Votre demande d’impression a été modifiée."
                    )
                    return redirect("teacher-print-detail", reference=item.reference)
            except Exception:
                for path in uploaded:
                    private_storage().delete(path)
                raise
    response = page(
        request,
        "printing.html",
        active="printing",
        form=form,
        documents=documents,
        editing=True,
        item=item,
        page_title="Modifier ma demande d’impression",
        description="Conservez vos PDF ou remplacez-les, puis ajustez les dates et les exemplaires.",
    )
    response.status_code = response_status
    return response


@teacher_required
@require_http_methods(["GET", "POST"])
def delete(request, reference):
    item = owned_request(request, reference)
    if item.statut != "En attente":
        return locked_response(request, item)
    form = PrintDeleteForm(
        request.POST if request.method == "POST" else None,
        initial={"revision": item.modifie_le.isoformat()},
    )
    response_status = 200
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            current = owned_request(request, reference, lock=True)
            if current.statut != "En attente":
                return locked_response(request, current)
            if form.cleaned_data["revision"] != current.modifie_le.isoformat():
                form.add_error(
                    None,
                    "Cette demande a changé. Rechargez la page pour confirmer la suppression de la version actuelle.",
                )
                response_status = 409
            else:
                paths = {
                    current.document,
                    *current.documents.values_list("document", flat=True),
                }
                current.delete()
                transaction.on_commit(
                    lambda: purge_unused_files(paths, request), robust=True
                )
        if not form.errors:
            messages.success(request, "Votre demande d’impression a été supprimée.")
            return redirect("teacher-requests")
    response = page(
        request,
        "print_delete.html",
        active="printing",
        item=item,
        form=form,
        page_title="Supprimer ma demande d’impression",
    )
    response.status_code = response_status
    return response

from pathlib import Path
from urllib.parse import urlencode
import re
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    login as auth_login,
    logout as auth_logout,
    update_session_auth_hash,
)
from django.contrib.auth.forms import PasswordChangeForm
from django.core.paginator import Paginator
from django.core.validators import MaxLengthValidator
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from .models import Enseignant, DemandeImpression, DocumentImpression
from .printing_options import PRINT_OPTIONS, legacy_print_data, print_summary
from .teacher_forms import (
    TeacherLoginForm,
    AnonymousForm,
    PrintBatchForm,
    PrintDocuments,
)
from .teacher_access import teacher_required, teacher_profile, teacher_context, private
from .files import save_upload, private_storage, file_response
from .views import site, throttle


def safe_next(request):
    target = (
        request.POST.get("next") or request.GET.get("next") or reverse("teacher-home")
    )
    if len(target) > 2000 or not url_has_allowed_host_and_scheme(
        target, {request.get_host()}, require_https=request.is_secure()
    ):
        return reverse("teacher-home")
    return target


def page(request, template, **context):
    return private(
        site(
            request,
            "enseignants/" + template,
            teacher_context(request, context.pop("active", "home")) | context,
        )
    )


@require_http_methods(["GET", "POST"])
def login(request):
    if teacher_profile(request):
        return redirect("teacher-home")
    form = TeacherLoginForm(request.POST or None)
    target = safe_next(request)
    if request.method == "POST":
        ppr = request.POST.get("ppr", "").strip().upper()[:32]
        if throttle(request, "teacher-login:" + ppr, 10, 300) or throttle(
            request, "teacher-login-global", 60, 300
        ):
            form.add_error(None, "Trop de tentatives. Réessayez dans cinq minutes.")
        elif form.is_valid():
            profile = (
                Enseignant.objects.select_related("utilisateur")
                .filter(ppr=form.cleaned_data["ppr"])
                .first()
            )
            password = form.cleaned_data["password"]
            if profile and profile.changer_mot_de_passe:
                password = password.strip().upper()
            user = authenticate(
                request,
                username="enseignant_" + form.cleaned_data["ppr"],
                password=password,
            )
            if (
                user is not None
                and profile is not None
                and user.pk == profile.utilisateur_id
                and profile.actif
            ):
                auth_login(request, user)
                if profile.changer_mot_de_passe:
                    return redirect(
                        reverse("teacher-password") + "?" + urlencode({"next": target})
                    )
                return redirect(target)
            form.add_error(None, "PPR ou mot de passe incorrect, ou compte désactivé.")
    return private(
        site(request, "enseignants/login.html", {"form": form, "next_path": target})
    )


@require_POST
def logout(request):
    auth_logout(request)
    return private(redirect("teacher-login"))


class TeacherPasswordForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.fields:
            self.fields[name].validators.append(MaxLengthValidator(256))
            self.fields[name].widget.attrs["maxlength"] = 256

    def clean_new_password1(self):
        value = self.cleaned_data["new_password1"]
        if self.user.check_password(value) or (
            self.user.profil_enseignant.changer_mot_de_passe
            and self.user.check_password(value.strip().upper())
        ):
            from django.core.exceptions import ValidationError

            raise ValidationError(
                "Choisissez un mot de passe différent du mot de passe actuel."
            )
        return value

    def clean_old_password(self):
        if self.user.profil_enseignant.changer_mot_de_passe:
            self.cleaned_data["old_password"] = (
                self.cleaned_data["old_password"].strip().upper()
            )
        return super().clean_old_password()


@teacher_required(password_page=True)
@require_http_methods(["GET", "POST"])
def password(request):
    form = TeacherPasswordForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
            request.enseignant.changer_mot_de_passe = False
            request.enseignant.save(update_fields=["changer_mot_de_passe"])
        update_session_auth_hash(request, user)
        messages.success(request, "Votre nouveau mot de passe a été enregistré.")
        return redirect(safe_next(request))
    return page(
        request,
        "form.html",
        form=form,
        page_title="Choisir mon mot de passe",
        description="Pour protéger votre compte, remplacez le mot de passe initial par un mot de passe personnel.",
        submit_label="Enregistrer mon mot de passe",
        next_path=safe_next(request),
        active="password",
    )


@teacher_required
@require_GET
def home(request):
    profile = request.enseignant
    return page(
        request,
        "home.html",
        page_title="Mon espace enseignants",
        vehicles=profile.vehicules.count(),
        prints=profile.impressions.count(),
        administrative=profile.documents_administratifs.count(),
    )


@teacher_required
@require_http_methods(["GET", "POST"])
def anonymous(request):
    form = AnonymousForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if throttle(request, "anonymous:" + str(request.enseignant.pk), 5, 3600):
            form.add_error(None, "Limite d’envoi atteinte. Réessayez plus tard.")
        else:
            # No account, PPR, IP or session identifier is attached to the message.
            form.save()
            messages.success(
                request, "Votre message a été envoyé sans être associé à votre compte."
            )
            return redirect("teacher-anonymous")
    return page(
        request,
        "form.html",
        active="anonymous",
        form=form,
        page_title="Envoyer un message anonyme",
        description="Aucun nom, PPR ou lien vers votre compte n’est enregistré avec le message. Les journaux techniques du serveur peuvent toutefois conserver des traces de connexion.",
        submit_label="Envoyer le message",
    )


def original_filename(upload):
    return re.sub(r"[\x00-\x1f\x7f]", "", Path(upload.name.replace("\\", "/")).name)[
        :240
    ]


@teacher_required
@require_http_methods(["GET", "POST"])
def printing(request):
    data = request.POST.copy() if request.method == "POST" else None
    files = request.FILES.copy() if request.method == "POST" else None
    # Older single-document forms remain valid after installing this update.
    if data is not None and "documents-TOTAL_FORMS" not in data and "fichier" in files:
        data.update(
            {
                "documents-TOTAL_FORMS": "1",
                "documents-INITIAL_FORMS": "0",
                "type_travail": data.get("type_travail", "autre"),
            }
        )
        for field in ("exemplaires", "mode", "format_papier", "couleur"):
            data["documents-0-" + field] = data.get(field, "")
        files["documents-0-fichier"] = files["fichier"]
    # Older forms supplied one date for the batch. Copy it only where an
    # individual date was not submitted; an explicit blank remains an error.
    if data is not None and "date_souhaitee" in data:
        try:
            count = min(max(int(data.get("documents-TOTAL_FORMS", "0")), 0), 12)
        except ValueError:
            count = 0
        for index in range(count):
            key = f"documents-{index}-date_souhaitee"
            if key not in data:
                data[key] = data["date_souhaitee"]
    data = legacy_print_data(data)
    form = PrintBatchForm(data)
    documents = PrintDocuments(data, files, prefix="documents")
    if request.method == "POST":
        valid_form, valid_documents = form.is_valid(), documents.is_valid()
        if valid_form and valid_documents:
            if throttle(request, "printing:" + str(request.enseignant.pk), 10, 3600):
                form.add_error(None, "Limite d’envoi atteinte. Réessayez plus tard.")
            else:
                saved = []
                try:
                    options = []
                    for document_form in documents:
                        values = document_form.cleaned_data
                        if values.get("DELETE") or not values.get("fichier"):
                            continue
                        upload = values["fichier"]
                        path, _ = save_upload(upload, "impressions", max_mb=20)
                        saved.append(path)
                        options.append(
                            {
                                "document": path,
                                "nom_document": original_filename(upload),
                                "couleur": "NB",
                                **{key: values[key] for key in PRINT_OPTIONS},
                            }
                        )
                    with transaction.atomic():
                        obj = form.save(commit=False)
                        obj.enseignant = request.enseignant
                        for key, value in options[0].items():
                            setattr(obj, key, value)
                        # Retain a summary for legacy integrations; each child
                        # is the source of its type, supplies and deadline.
                        for key, value in print_summary(options).items():
                            setattr(obj, key, value)
                        obj.date_souhaitee = min(d["date_souhaitee"] for d in options)
                        obj.save()
                        DocumentImpression.objects.bulk_create(
                            [
                                DocumentImpression(demande=obj, **values)
                                for values in options
                            ]
                        )
                except Exception:
                    for path in saved:
                        private_storage().delete(path)
                    raise
                messages.success(
                    request,
                    "Votre demande d’impression a été envoyée. Retrouvez son avancement dans Mes demandes.",
                )
                return redirect("teacher-print-detail", reference=obj.reference)
    return page(
        request,
        "printing.html",
        active="printing",
        form=form,
        documents=documents,
        page_title="Demande d’impression",
        description="Un examen à préparer ou plusieurs documents à imprimer ? Envoyez votre demande ici.",
    )


@teacher_required
@require_GET
def requests(request):
    profile = request.enseignant
    return page(
        request,
        "requests.html",
        active="requests",
        page_title="Mes demandes",
        administrative_page=Paginator(
            profile.documents_administratifs.all(), 15
        ).get_page(request.GET.get("administratifs")),
        vehicle_page=Paginator(profile.vehicules.all(), 15).get_page(
            request.GET.get("vehicules")
        ),
        print_page=Paginator(
            profile.impressions.prefetch_related("documents"), 15
        ).get_page(request.GET.get("impressions")),
    )


@teacher_required
@require_GET
def print_detail(request, reference):
    obj = get_object_or_404(
        DemandeImpression, reference=reference, enseignant=request.enseignant
    )
    return page(
        request,
        "print_detail.html",
        active="printing",
        page_title="Ma demande d’impression",
        item=obj,
    )


def print_request_for_user(request, reference):
    qs = DemandeImpression.objects.all()
    user = request.user
    if not (
        user.is_authenticated
        and user.is_active
        and user.is_staff
        and user.has_perm("portal.view_demandeimpression")
    ):
        qs = qs.filter(enseignant=request.enseignant)
    return get_object_or_404(qs, reference=reference)


def _print_download(request, reference, document_id=None):
    obj = print_request_for_user(request, reference)
    document = (
        get_object_or_404(obj.documents, pk=document_id)
        if document_id is not None
        else obj
    )
    return private(
        file_response(
            document.document,
            filename=document.nom_document,
            mime="application/pdf",
            download=True,
            request=request,
        )
    )


@require_GET
def print_file(request, reference, document_id=None):
    user = request.user
    if (
        user.is_authenticated
        and user.is_active
        and user.is_staff
        and user.has_perm("portal.view_demandeimpression")
    ):
        return _print_download(request, reference, document_id)
    return _teacher_print_file(request, reference, document_id)


@teacher_required
@require_GET
def _teacher_print_file(request, reference, document_id=None):
    return _print_download(request, reference, document_id)

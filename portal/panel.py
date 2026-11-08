"""Administration EST-FBS : interface Laravel d'origine, traitements Django."""

import json
from functools import wraps
from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST
from markupsafe import Markup

from .models import (
    Publication,
    Professeur,
    Photo,
    EmploiDuTemps,
    Reglement,
    DemandeEtudiant,
    DemandePersonnel,
    MessageContact,
    DemandeVehicule,
    REQUEST_STATUSES,
    Etudiant,
)
from .forms import (
    PublicationForm,
    ProfesseurForm,
    PhotoForm,
    EmploiForm,
    ReglementForm,
    EtudiantForm,
)
from .files import file_response, find_file, save_upload
from .richtext import delta_document, render_content
from .validators import valid_link
from .views import site, staff, visitor_stats
from .panel_covers import clean_design
from .jinja import fmt_date

MODULES = {
    "etudiants": (Etudiant, EtudiantForm, "etudiant", "etudiant", "Étudiants (Apogée)"),
    "publications": (
        Publication,
        PublicationForm,
        "publication",
        "publication",
        "Actualités & événements",
    ),
    "professeurs": (
        Professeur,
        ProfesseurForm,
        "professeur",
        "professeur",
        "Nos professeurs",
    ),
    "photos": (Photo, PhotoForm, "photo", "photo", "Galerie photos & vidéos"),
    "emplois": (
        EmploiDuTemps,
        EmploiForm,
        "emploidutemps",
        "emploi",
        "Emplois du temps",
    ),
    "reglements": (
        Reglement,
        ReglementForm,
        "reglement",
        "reglement",
        "Textes et règlements",
    ),
}
SECTIONS = {"emplois": "emplois-du-temps", "reglements": "textes-reglements"}


def permitted(user, module, action="view"):
    return user.has_perm("portal." + action + "_" + MODULES[module][2])


def guarded(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not staff(request):
            return redirect_to_login(request.get_full_path(), reverse("panel-login"))
        response = view(request, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        response["Referrer-Policy"] = "same-origin"
        return response

    return wrapped


def panel_route(name, params=None, absolute=False):
    from .jinja import route as public_route

    if name == "admin.dashboard":
        return reverse("panel-dashboard")
    if name == "admin.cover_creator":
        return reverse("panel-cover-creator")
    if name in ("login", "login.store"):
        return reverse("panel-login")
    if name == "logout":
        return reverse("panel-logout")
    if name.startswith("admin.") and name.split(".")[1] in MODULES:
        _, module, action = name.split(".")
        action = {"create": "create", "store": "create", "update": "edit"}.get(
            action, action
        )
        kwargs = {"module": module}
        if action in ("edit", "toggle", "destroy"):
            kwargs["pk"] = params.pk if hasattr(params, "pk") else params
        return reverse("panel-" + action, kwargs=kwargs)
    return public_route(name, params, absolute)


def pagination(request, page, parameter="page", tab=None):
    from django.utils.html import format_html

    links = []
    for number, label in [
        (page.previous_page_number() if page.has_previous() else None, "← Précédent"),
        (page.next_page_number() if page.has_next() else None, "Suivant →"),
    ]:
        if number:
            query = request.GET.copy()
            query[parameter] = str(number)
            if tab:
                query["tab"] = tab
            links.append(
                str(
                    format_html(
                        '<a class="pub-btn secondary" href="?{}">{}</a>',
                        query.urlencode(),
                        label,
                    )
                )
            )
    return Markup(
        '<nav class="pub-pagination" aria-label="Pagination">'
        + "".join(links)
        + f"<span>Page {page.number} / {page.paginator.num_pages}</span></nav>"
    )


def admin_context(request, **extra):
    form = extra.get("form")
    instance = extra.get("instance")

    def old(name, default=""):
        aliases = {
            "remove_image": "supprimer_image",
            "remove_photo": "supprimer_photo",
            "image": "image_upload",
            "photo": "photo_upload",
            "fichier": "fichier_upload",
            "vignette": "vignette_upload",
        }
        target = aliases.get(name, name)
        if form and form.is_bound:
            if target in form.fields:
                if isinstance(form.fields[target], forms.BooleanField):
                    return str(form.data.get(target, "")).lower() in ("true", "1", "on")
                value = form.data.get(target, default)
                return "" if value is None else value
        return "" if default is None else default

    context = {
        "route": panel_route,
        "admin_name": (
            (request.user.get_full_name() or request.user.get_username())
            if request.user.is_authenticated
            else ""
        ),
        "admin_role": (
            "Super administrateur" if request.user.is_superuser else "Administrateur"
        ),
        "section": extra.get("section", ""),
        "query": request.GET,
        "old": old,
        "now": timezone.now(),
        "getattr": getattr,
        "valid_link": valid_link,
        "cycles": dict(EmploiDuTemps.CYCLES),
        "fmt_date": lambda value, fmt="d/m/Y": fmt_date(
            (
                timezone.localtime(value)
                if hasattr(value, "hour") and timezone.is_aware(value)
                else value
            ),
            fmt,
        ),
        "shorten": lambda s, n: (s[: n - 1] + "…") if len(s) > n else s,
        "form_errors": (
            [str(e) for values in form.errors.values() for e in values] if form else []
        ),
        "status_message": "",
        "professor_fields": {
            "grade": ["Grade / fonction", 120],
            "departement": ["Département", 150],
            "specialite": ["Spécialité", 180],
            "email": ["Email professionnel", 150],
        },
        "pagination": lambda page: pagination(request, page),
        "dashboard_pagination": lambda key, page: pagination(
            request, page, key + "_page", key
        ),
        "can": lambda module, action="view": permitted(request.user, module, action),
        "can_model": lambda model, action="view": request.user.has_perm(
            "portal." + action + "_" + model
        ),
        "status_badge": lambda value: {
            "Prête": "bg-emerald-100 text-emerald-800 border-emerald-300",
            "En cours": "bg-amber-100 text-slate-800 border-slate-300",
            "Rejetée": "bg-red-100 text-red-800 border-red-300",
        }.get(value, "bg-amber-100 text-amber-800 border-amber-300"),
    }
    context.update(extra)
    return context


def panel_page(request, template, **context):
    status = context.pop("http_status", 200)
    return site(request, template, admin_context(request, **context), status=status)


@guarded
@require_http_methods(["GET"])
def cover_creator(request):
    if not (
        permitted(request.user, "publications", "add")
        or permitted(request.user, "publications", "change")
    ):
        raise PermissionDenied
    obj = None
    source = request.GET.get("publication", "")
    if source:
        if not permitted(request.user, "publications", "change"):
            raise PermissionDenied
        if (
            not source.isascii()
            or not source.isdigit()
            or len(source) > 19
            or not 1 <= int(source) <= 9223372036854775807
        ):
            raise Http404
        obj = get_object_or_404(Publication, pk=int(source))
    saved = obj.cover_design if obj and isinstance(obj.cover_design, dict) else {}
    try:
        design = clean_design(saved) if saved else None
    except forms.ValidationError:
        design = None
    return panel_page(
        request,
        "admin/covers/create.html",
        section="cover_creator",
        page_title="Créateur d’images",
        standalone=True,
        saved_cover=saved,
        initial_cover=design,
        initial_cover_json=json.dumps(design, ensure_ascii=False),
        cover_retry=False,
        cover_asset_url=lambda kind: (
            reverse(
                "panel-cover-asset",
                args=[obj.pk, "background" if kind == "backgroundAsset" else "logo"],
            )
            if obj and saved.get(kind)
            else ""
        ),
    )


@require_http_methods(["GET", "POST"])
def login(request):
    if staff(request):
        return redirect("panel-dashboard")
    form = AdminAuthenticationForm(
        request, data=request.POST if request.method == "POST" else None
    )
    if request.method == "POST" and form.is_valid():
        auth_login(request, form.get_user())
        destination = request.POST.get("next", "")
        if not url_has_allowed_host_and_scheme(
            destination,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            destination = reverse("panel-dashboard")
        return redirect(destination or reverse("panel-dashboard"))
    return panel_page(
        request,
        "admin/login.html",
        form=form,
        error="",
        next=request.GET.get("next", ""),
        http_status=200,
    )


@require_POST
def logout(request):
    auth_logout(request)
    return redirect("panel-login")


@guarded
@require_http_methods(["GET", "POST"])
def dashboard(request):
    if request.method == "POST":
        actions = {
            "update_status_etudiant": (DemandeEtudiant, "demandeetudiant", "etudiants"),
            "update_status_pers": (DemandePersonnel, "demandepersonnel", "personnel"),
            "update_message_status": (MessageContact, "messagecontact", "contact"),
            "update_vehicle_status": (DemandeVehicule, "demandevehicule", "vehicules"),
        }
        action = actions.get(request.POST.get("action"))
        if not action:
            return HttpResponse("Action inconnue.", status=400)
        model, code, tab = action
        if not request.user.has_perm("portal.change_" + code):
            raise PermissionDenied
        status = request.POST.get("status", "")
        field = model._meta.get_field("statut")
        if status not in dict(field.choices):
            return HttpResponse("Statut invalide.", status=400)
        try:
            pk = int(request.POST.get("id", ""))
        except ValueError:
            raise Http404
        obj = get_object_or_404(model, pk=pk)
        obj.statut = status
        if hasattr(obj, "date_mise_a_jour"):
            obj.date_mise_a_jour = timezone.now()
        if hasattr(obj, "updated_at"):
            obj.updated_at = timezone.now()
        if model is DemandeVehicule:
            obj.remarque_administration = request.POST.get(
                "remarque_administration", ""
            )[:10000]
        obj.save()
        messages.success(request, "Le statut a été mis à jour.")
        return redirect(reverse("panel-dashboard") + "?tab=" + tab)
    q = request.GET.get("q", "").strip()[:150]
    status = request.GET.get("filter_status", "all")

    def rows(model, name, fields):
        queryset = (
            model.objects.all()
            if request.user.has_perm("portal.view_" + name)
            else model.objects.none()
        )
        if q:
            predicate = Q()
            for field in fields:
                predicate |= Q(**{field + "__icontains": q})
            queryset = queryset.filter(predicate)
        if status != "all":
            queryset = queryset.filter(statut=status)
        return queryset

    students = rows(
        DemandeEtudiant,
        "demandeetudiant",
        ["nom_prenom", "cne", "code_suivi", "filiere"],
    )
    personnel = rows(
        DemandePersonnel, "demandepersonnel", ["nom_prenom", "ppr", "code_suivi"]
    )
    contacts = rows(
        MessageContact,
        "messagecontact",
        ["nom_complet", "apogee", "email", "sujet", "message"],
    )
    vehicles = rows(
        DemandeVehicule,
        "demandevehicule",
        ["nom_professeur", "code_suivi", "destination"],
    )
    pages = {
        key: Paginator(query, 30).get_page(request.GET.get(key + "_page"))
        for key, query in [
            ("etudiants", students),
            ("personnel", personnel),
            ("contact", contacts),
            ("vehicules", vehicles),
        ]
    }
    return panel_page(
        request,
        "admin/dashboard.html",
        demandes_etudiants=pages["etudiants"],
        demandes_personnel=pages["personnel"],
        messages_contact=pages["contact"],
        demandes_vehicule=pages["vehicules"],
        dashboard_pages=pages,
        search_query=q,
        filter_status=status,
        feedback="",
        panel_stats={
            "total_etudiants": students.count(),
            "en_attente_etudiants": students.filter(statut="En attente").count(),
            "pretes_etudiants": students.filter(statut="Prête").count(),
            "nouveaux_messages": contacts.filter(statut="Nouveau").count(),
        },
        visitorStats=(
            visitor_stats(request)
            if request.user.has_perm("portal.view_sitevisit")
            else None
        ),
    )


@guarded
@require_http_methods(["GET"])
def listing(request, module):
    model, formclass, code, object_name, title = MODULES[module]
    if not permitted(request.user, module):
        raise PermissionDenied
    query = model.objects.all()
    q = request.GET.get("q", "").strip()[:150]
    fields = {
        "etudiants": ["apogee", "nom", "prenom", "filiere"],
        "publications": ["titre", "categorie", "resume"],
        "professeurs": ["nom", "prenom", "departement", "specialite"],
        "photos": ["titre", "categorie", "legende"],
        "emplois": ["filiere", "annee"],
        "reglements": ["titre"],
    }[module]
    if q:
        predicate = Q()
        for field in fields:
            predicate |= Q(**{field + "__icontains": q})
        query = query.filter(predicate)
    if module == "publications":
        status = request.GET.get("statut", "")
        if status == "publie":
            query = query.published()
        elif status == "programme":
            query = query.filter(publie=True, date_publication__gt=timezone.now())
        elif status == "brouillon":
            query = query.filter(publie=False)
        elif status == "expire":
            query = query.expired()
    if module == "photos" and request.GET.get("type") in ("image", "video"):
        query = query.filter(type=request.GET["type"])
    page = Paginator(query, 20).get_page(request.GET.get("page"))
    collection = {
        "etudiants": "etudiants",
        "publications": "publications",
        "professeurs": "professeurs",
        "photos": "photos",
        "emplois": "emplois",
        "reglements": "documents",
    }[module]
    stats = {}
    if module == "publications":
        stats = {
            "Total": model.objects.count(),
            "En ligne": model.objects.published().count(),
            "Brouillons": model.objects.filter(publie=False).count(),
            "Programmées": model.objects.filter(
                publie=True, date_publication__gt=timezone.now()
            ).count(),
        }
    return panel_page(
        request,
        "admin/" + module + "/index.html",
        section=module,
        page_title=title,
        page=page,
        **{collection: page},
        panel_stats=stats,
    )


def adapted_data(request, module, obj):
    data = request.POST.copy()
    files = request.FILES.copy()
    for before, after in {
        "remove_image": "supprimer_image",
        "remove_photo": "supprimer_photo",
    }.items():
        if before in data:
            data[after] = data[before]
    for name in (
        "publie",
        "afficher_bouton",
        "bouton_nouvel_onglet",
        "supprimer_image",
        "supprimer_photo",
        "generer_visuel",
    ):
        data[name] = "True" if data.get(name, "").lower() in ("true", "1", "on") else ""
    aliases = {
        "etudiants": {},
        "publications": {"image": "image_upload"},
        "professeurs": {"photo": "photo_upload"},
        "photos": {"fichier": "fichier_upload", "vignette": "vignette_upload"},
        "emplois": {f"fichier_s{i}": f"fichier_lien_s{i}" for i in range(1, 7)},
        "reglements": {"fichier": "document"},
    }[module]
    for before, after in aliases.items():
        if before in files:
            files[after] = files[before]
    if module == "emplois":
        for name in ["niveau", "lien"] + [f"lien_s{i}" for i in range(1, 7)]:
            if name not in data:
                data[name] = getattr(obj, name, "") or ""
    if module == "publications" and "suppression_apres_jours" not in data:
        data["suppression_apres_jours"] = obj.suppression_apres_jours or ""
    if module == "reglements" and "legacy_url" not in data:
        data["legacy_url"] = obj.legacy_url
    return data, files


@guarded
@require_http_methods(["GET", "POST"])
def editor(request, module, pk=None):
    model, formclass, code, object_name, title = MODULES[module]
    action = "change" if pk is not None else "add"
    if not permitted(request.user, module, action):
        raise PermissionDenied
    obj = get_object_or_404(model, pk=pk) if pk is not None else model()
    if module == "publications":
        from .panel_forms import ComposedPublicationForm

        formclass = ComposedPublicationForm
    data, files = (
        adapted_data(request, module, obj) if request.method == "POST" else (None, None)
    )
    form = formclass(data, files, instance=obj)
    if module == "publications" and not permitted(
        request.user, "publications", "delete"
    ):
        form.fields["suppression_apres_jours"].disabled = True
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            saved = form.save()
            if (
                module == "photos"
                and request.POST.get("remove_vignette") == "1"
                and not files.get("vignette_upload")
            ):
                saved.vignette = ""
                saved.save(update_fields=["vignette"])
        messages.success(request, "Les modifications ont été enregistrées.")
        return redirect(panel_route("admin." + module + ".index"))
    extra = {}
    if module == "publications":
        saved_cover = (
            obj.cover_design
            if isinstance(obj.cover_design, dict)
            and obj.cover_design.get("version") == 1
            and isinstance(obj.cover_design.get("texts"), list)
            else None
        )
        initial_cover = saved_cover
        if data and data.get("cover_design"):
            try:
                initial_cover = clean_design(json.loads(data["cover_design"]))
            except (ValueError, TypeError, forms.ValidationError):
                pass
        delta = data.get("contenu_delta") if data is not None else obj.contenu_delta
        delta = delta_document(delta)
        initial_text = data.get("contenu", "") if data is not None else obj.contenu
        extra = {
            "initial_delta": json.dumps(delta, ensure_ascii=False) if delta else "",
            "initial_text": initial_text,
            "initial_html": str(render_content(delta, initial_text)),
            "saved_cover": saved_cover or {},
            "initial_cover": initial_cover,
            "initial_cover_json": json.dumps(initial_cover, ensure_ascii=False),
            "cover_retry": bool(data and data.get("cover_design")),
            "cover_asset_url": lambda kind: (
                reverse(
                    "panel-cover-asset",
                    args=[
                        obj.pk,
                        "background" if kind == "backgroundAsset" else "logo",
                    ],
                )
                if obj.pk and saved_cover and saved_cover.get(kind)
                else ""
            ),
        }
    return panel_page(
        request,
        "admin/" + module + "/form.html",
        section=module,
        form=form,
        instance=obj,
        **{object_name: obj},
        **extra,
        http_status=422 if form.is_bound else 200,
    )


@guarded
@require_POST
def toggle(request, module, pk):
    if not permitted(request.user, module, "change"):
        raise PermissionDenied
    obj = get_object_or_404(MODULES[module][0], pk=pk)
    if module == "etudiants":
        obj.actif = not obj.actif
        obj.save(update_fields=["actif", "modifie_le"])
        messages.success(request, "L’autorisation de l’étudiant a été mise à jour.")
        return redirect(panel_route("admin.etudiants.index"))
    obj.publie = not obj.publie
    if isinstance(obj, Publication):
        obj.modifie_le = timezone.now()
    obj.save()
    messages.success(request, "La visibilité a été mise à jour.")
    return redirect(panel_route("admin." + module + ".index"))


@guarded
@require_POST
def destroy(request, module, pk):
    if not permitted(request.user, module, "delete"):
        raise PermissionDenied
    obj = get_object_or_404(MODULES[module][0], pk=pk)
    obj.delete()
    messages.success(request, "L’élément a été supprimé.")
    return redirect(panel_route("admin." + module + ".index"))


@guarded
@require_http_methods(["GET", "HEAD"])
def cover_asset(request, pk, kind):
    if not permitted(request.user, "publications"):
        raise PermissionDenied
    if kind not in ("background", "logo"):
        raise Http404
    obj = get_object_or_404(Publication, pk=pk)
    path = (obj.cover_design or {}).get(kind + "Asset", "")
    if not isinstance(path, str) or not path.startswith(
        ("uploads/", "covers/", "publications/")
    ):
        raise Http404
    return file_response(path, request=request)

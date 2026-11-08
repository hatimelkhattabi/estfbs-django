import io
import json
import re
import secrets
from datetime import timedelta
from collections import OrderedDict
from pathlib import Path
from html import escape
from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse, Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.http import require_GET, require_POST, require_http_methods
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
)
from .forms import StudentForm, PersonnelForm, ContactForm, VehicleForm
from .files import file_response, save_document
from .validators import valid_link
from .teacher_access import teacher_required, visible_vehicles, teacher_context


def site(request, template, context=None, status=200):
    return render(request, template, context or {}, status=status, using="site")


def staff(request):
    return (
        request.user.is_authenticated
        and request.user.is_active
        and request.user.is_staff
    )


def throttle(request, key, limit=10, seconds=60):
    token = (
        key
        + ":"
        + salted_hmac("throttle", request.META.get("REMOTE_ADDR", "")).hexdigest()
    )
    if cache.add(token, 1, seconds):
        return False
    try:
        n = cache.incr(token)
    except ValueError:
        cache.set(token, 1, seconds)
        n = 1
    return n > limit


def home(request):
    return site(
        request,
        "home.html",
        {
            "publications": list(Publication.objects.published()[:3]),
            "professeurs": list(Professeur.objects.filter(publie=True)),
            "medias": list(Photo.objects.filter(publie=True, type="image")[:8]),
            "previewGallery": True,
        },
    )


def page(request, name):
    return site(request, "pages/" + name + ".html")


def archive(request):
    query = Publication.objects.published()
    kind = request.GET.get("type", "")
    q = request.GET.get("q", "").strip()[:150]
    if kind in ["Actualité", "Événement"]:
        query = query.filter(type=kind)
    if q:
        query = query.filter(
            Q(titre__icontains=q)
            | Q(resume__icontains=q)
            | Q(categorie__icontains=q)
            | Q(contenu__icontains=q)
        )
    page = Paginator(query, 12).get_page(request.GET.get("page"))
    return site(
        request,
        "publications/archive.html",
        {"publications": page, "q": q, "kind": kind},
    )


def publication(request, pk):
    obj = get_object_or_404(Publication, pk=pk)
    preview = staff(request) and request.GET.get("preview") == "1"
    if not preview and not obj.visible:
        raise Http404
    response = site(
        request, "publications/show.html", {"publication": obj, "preview": preview}
    )
    response["Cache-Control"] = "private, no-store"
    return response


def legacy_publication(request):
    try:
        pk = int(request.GET.get("id", ""))
    except ValueError:
        raise Http404
    return publication(request, pk)


def publication_image(request, pk=None, filename=None):
    if pk is not None:
        obj = get_object_or_404(Publication, pk=pk)
    else:
        obj = Publication.objects.filter(image__endswith="/" + str(filename)).first()
    if not obj or not (obj.visible or staff(request)) or not obj.image:
        raise Http404
    return file_response(obj.image, request=request)


@require_GET
def publication_api(request):
    query = Publication.objects.published()
    q = request.GET.get("q", "").strip()[:150]
    if q:
        query = query.filter(
            Q(titre__icontains=q)
            | Q(resume__icontains=q)
            | Q(categorie__icontains=q)
            | Q(contenu__icontains=q)
        )
    rows = [
        {
            "id": p.pk,
            "type": p.type,
            "titre": p.titre,
            "categorie": p.categorie,
            "resume": p.resume,
            "image": p.image_url,
            "image_url": p.image_url,
            "lieu": p.lieu,
            "date_evenement": p.date_evenement,
            "date_publication": p.date_publication,
            "url": reverse("publication", args=[p.pk]),
        }
        for p in query[:100]
    ]
    return JsonResponse({"success": True, "data": rows})


def professeurs(request):
    return site(
        request,
        "pages/professeurs.html",
        {"professeurs": list(Professeur.objects.filter(publie=True))},
    )


def professeur(request, pk):
    obj = get_object_or_404(Professeur, pk=pk)
    if not obj.publie and not staff(request):
        raise Http404
    return site(request, "professeurs/show.html", {"professeur": obj})


def professeur_photo(request, pk):
    obj = get_object_or_404(Professeur, pk=pk)
    if not (obj.publie or staff(request)) or not obj.photo:
        raise Http404
    return file_response(obj.photo, request=request)


def legacy_professeur(request):
    p = Professeur.objects.filter(publie=True, nom__icontains="LAASSIRI").first()
    return redirect("professeur", pk=p.pk) if p else redirect("professeurs")


def galerie(request):
    q = Photo.objects.filter(publie=True)
    if request.GET.get("type") in ["image", "video"]:
        q = q.filter(type=request.GET["type"])
    return site(
        request,
        "galerie/index.html",
        {
            "medias": Paginator(q, 24).get_page(request.GET.get("page")),
            "previewGallery": False,
        },
    )


def media_file(request, pk, thumbnail=False):
    obj = get_object_or_404(Photo, pk=pk)
    if not obj.publie and not staff(request):
        raise Http404
    path = obj.vignette if thumbnail else obj.fichier
    if not path:
        raise Http404
    return file_response(path, request=request)


def emplois(request):
    groups = OrderedDict()
    for row in EmploiDuTemps.objects.filter(publie=True):
        groups.setdefault(row.annee, OrderedDict()).setdefault(row.cycle, []).append(
            row
        )
    return site(
        request,
        "emplois/index.html",
        {
            "annees": groups,
            "cycle_labels": dict(EmploiDuTemps.CYCLES),
            "valid_link": valid_link,
        },
    )


def reglements(request):
    return site(
        request,
        "pages/textes-reglements.html",
        {"documents": list(Reglement.objects.filter(publie=True))},
    )


def reglement_document(request, pk):
    obj = get_object_or_404(Reglement, pk=pk)
    if not obj.publie and not staff(request):
        raise Http404
    if obj.file_path:
        return file_response(obj.file_path, obj.original_name or None, request=request)
    if valid_link(obj.legacy_url):
        return redirect(obj.legacy_url)
    raise Http404


def document_available(obj):
    uid = str(obj.pk)
    if (
        Publication.objects.published()
        .filter(
            Q(contenu__icontains=uid)
            | Q(contenu_delta__icontains=uid)
            | Q(afficher_bouton=True, lien__icontains=uid)
        )
        .exists()
    ):
        return True
    q = Q(lien__icontains=uid)
    for i in range(1, 7):
        q |= Q(**{f"lien_s{i}__icontains": uid})
    for row in EmploiDuTemps.objects.filter(publie=True).filter(q):
        if any(uid in (value or "") for _, value in row.liens):
            return True
        if row.cycle == "Bachelor" and uid in row.lien:
            return True
    return False


def document(request, uid):
    obj = get_object_or_404(UploadedDocument, pk=uid)
    if not staff(request) and not document_available(obj):
        raise Http404
    return file_response(obj.path, obj.original_name, obj.mime, request=request)


@require_POST
def document_upload(request):
    if not staff(request) or not any(
        request.user.has_perm("portal." + action + "_" + model)
        for action in ("add", "change")
        for model in ("publication", "emploidutemps", "reglement")
    ):
        return JsonResponse(
            {"success": False, "message": "Connexion administrateur requise."},
            status=403,
        )
    if throttle(request, "upload", 60):
        return JsonResponse(
            {
                "success": False,
                "message": "Trop de fichiers envoyés. Réessayez dans une minute.",
            },
            status=429,
        )
    f = request.FILES.get("fichier")
    if not f:
        return JsonResponse(
            {"success": False, "message": "Choisissez un fichier."}, status=422
        )
    from django.core.exceptions import ValidationError

    try:
        obj = save_document(f, request.user)
    except ValidationError as e:
        return JsonResponse(
            {"success": False, "message": " ".join(e.messages)}, status=422
        )
    return JsonResponse(
        {"success": True, "url": obj.url, "nom": obj.original_name}, status=201
    )


def request_data(request):
    if request.content_type == "application/json":
        try:
            value = json.loads(request.body)
            return value if isinstance(value, dict) else {}
        except (ValueError, UnicodeError):
            return {}
    return request.POST.dict()


@require_POST
def submit(request, kind):
    if throttle(request, "submit-" + kind, 8 if kind != "contact" else 5):
        return JsonResponse(
            {
                "success": False,
                "message": "Trop de demandes. Réessayez dans une minute.",
            },
            status=429,
        )
    d = request_data(request)
    if kind == "student":
        d["nom_prenom"] = d.get("nom", d.get("nom_prenom", ""))
        d["type_document"] = d.get("document", d.get("type_document", ""))
        form = StudentForm(d)
    elif kind == "personnel":
        d["nom_prenom"] = d.get("nom", d.get("nom_prenom", ""))
        d["type_attestation"] = d.get("type_attestation", d.get("attestation", ""))
        form = PersonnelForm(d)
    else:
        d["nom_complet"] = d.get("nom", d.get("nom_complet", ""))
        form = ContactForm(d)
    if not form.is_valid():
        return JsonResponse(
            {
                "success": False,
                "message": "Vérifiez les champs du formulaire.",
                "errors": form.errors.get_json_data(),
            },
            status=422,
        )
    obj = form.save()
    if kind == "contact" and settings.CONTACT_EMAIL:
        send_mail(
            "Contact EST-FBS : " + re.sub(r"[\r\n]+", " ", obj.sujet),
            f"{obj.nom_complet}\nEmail : {obj.email}\nApogée : {obj.apogee}\n\n{obj.message}",
            settings.DEFAULT_FROM_EMAIL,
            [settings.CONTACT_EMAIL],
            fail_silently=True,
        )
    code = getattr(obj, "code_suivi", None)
    data = {"success": True, "message": "Votre demande a été enregistrée."}
    if kind == "contact":
        data["message"] = "Votre message a bien été envoyé à l’administration."
    if code:
        data.update({"code_suivi": code, "data": {"code_suivi": code}})
    return JsonResponse(data, status=201)


def find_tracking(request):
    d = request.GET if request.method == "GET" else request_data(request)
    code = str(d.get("code", "")).strip()
    result = {"code": code, "demande": None, "error": ""}
    if not code:
        return result
    if code.startswith("ESTFBS-VEH-"):
        record = visible_vehicles(request).filter(code_suivi=code).first()
        if record:
            result["demande"] = {
                "code_suivi": code,
                "type_document": "Demande de véhicule",
                "statut": record.statut,
                "date_demande": record.date_demande,
                "pdf_url": reverse("vehicule-pdf", args=[code]),
            }
    elif re.fullmatch(r"(ESTFBS|PERS)-([a-fA-F0-9]{24}|[0-9]{6})", code):
        model = DemandePersonnel if code.startswith("PERS-") else DemandeEtudiant
        q = model.objects.filter(code_suivi=code)
        if re.search(r"-\d{6}$", code):
            identity = str(d.get("identifiant", "")).strip().upper()
            if not identity:
                result["error"] = (
                    "Renseignez aussi votre CNE ou PPR pour cet ancien code."
                )
                return result
            q = q.filter(
                **(
                    {"ppr": identity}
                    if model is DemandePersonnel
                    else {"cne": identity}
                )
            )
        record = q.first()
        if record:
            result["demande"] = {
                "code_suivi": code,
                "type_document": (
                    record.type_attestation
                    if model is DemandePersonnel
                    else record.type_document
                ),
                "statut": record.statut,
                "date_demande": record.date_demande,
            }
    if not result["demande"]:
        result["error"] = (
            "Aucune demande trouvée. Vérifiez le code de suivi et, si nécessaire, votre identifiant."
        )
    return result


def tracking(request, api=False):
    if throttle(request, "tracking", 30):
        return JsonResponse(
            {"success": False, "message": "Veuillez réessayer dans une minute."},
            status=429,
        )
    result = find_tracking(request)
    if api:
        response = JsonResponse(
            {
                "success": bool(result["demande"]),
                "message": result["error"],
                "count": 1 if result["demande"] else 0,
                "demandes": [result["demande"]] if result["demande"] else [],
            }
        )
    else:
        response = site(request, "tracking.html", result)
    response["Cache-Control"] = "private, no-store"
    response["Referrer-Policy"] = "no-referrer"
    return response


def personnel(request):
    return site(request, "personnel.html")


@teacher_required
@require_http_methods(["GET", "POST"])
def vehicule(request):
    profile = request.enseignant
    identity = {
        "nom_professeur": profile.nom_complet,
        "email_professeur": profile.email,
        "departement": profile.departement,
        "grade_professeur": profile.grade or "PES",
    }
    data = request_data(request) if request.method == "POST" else None
    if data is not None:
        data.update(
            {
                key: value
                for key, value in identity.items()
                if key == "nom_professeur"
                or getattr(
                    profile,
                    {
                        "grade_professeur": "grade",
                        "email_professeur": "email",
                        "departement": "departement",
                    }.get(key, key),
                    "",
                )
            }
        )
    form = VehicleForm(data, initial=identity)
    form.instance.enseignant = profile
    if request.method == "POST":
        if throttle(request, "vehicle", 8):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Veuillez patienter avant une nouvelle demande.",
                },
                status=429,
            )
        if form.is_valid():
            obj = form.save()
            url = reverse("vehicule-status", args=[obj.code_suivi])
            pdf = reverse("vehicule-pdf", args=[obj.code_suivi])
            mission = reverse("vehicule-mission-pdf", args=[obj.code_suivi])
            if (
                "application/json" in request.headers.get("Accept", "")
                or request.content_type == "application/json"
            ):
                return JsonResponse(
                    {
                        "success": True,
                        "code_suivi": obj.code_suivi,
                        "statut": obj.statut,
                        "message": "Votre demande a été enregistrée. L’ordre de mission sera disponible après validation par l’administration.",
                        "ordre_mission_disponible": obj.ordre_mission_disponible,
                        "ordre_mission_pdf_url": (
                            mission if obj.ordre_mission_disponible else None
                        ),
                        "ordre_mission_download_url": (
                            mission + "?download=1"
                            if obj.ordre_mission_disponible
                            else None
                        ),
                        "data": {
                            "nom_professeur": obj.nom_professeur,
                            "destination": obj.destination,
                            "date_visite": obj.date_visite.strftime("%d/%m/%Y"),
                            "effectif_etudiants": obj.effectif_etudiants,
                        },
                        "status_url": url,
                        "pdf_url": pdf,
                        "pdf_download_url": pdf + "?download=1",
                    },
                    status=201,
                )
            messages.success(request, "Votre demande de véhicule a été enregistrée.")
            return redirect(url)
        if (
            "application/json" in request.headers.get("Accept", "")
            or request.content_type == "application/json"
        ):
            return JsonResponse(
                {"success": False, "errors": form.errors.get_json_data()}, status=422
            )
    return site(
        request,
        "vehicule/demande.html",
        vehicle_context(form) | teacher_context(request, "vehicle"),
        status=422 if request.method == "POST" else 200,
    )


@teacher_required(allow_manager=True)
@require_GET
def vehicule_status(request, code):
    from .vehicles import professor_name

    obj = get_object_or_404(visible_vehicles(request), code_suivi=code)
    response = site(
        request,
        "vehicule/status.html",
        {"demande": obj, "professor_name": professor_name(obj.nom_professeur)}
        | teacher_context(request, "vehicle"),
    )
    response["Cache-Control"] = "private, no-store"
    response["Referrer-Policy"] = "no-referrer"
    return response


@teacher_required(allow_manager=True)
@require_GET
def vehicule_suivi(request):
    from .vehicles import professor_name

    code = request.GET.get("code", "").strip().upper()
    obj = visible_vehicles(request).filter(code_suivi=code).first() if code else None
    response = site(
        request,
        "vehicule/suivi.html",
        {
            "code": code,
            "demande": obj,
            "professor_name": professor_name(obj.nom_professeur) if obj else "",
            "error": "Aucune demande trouvée avec ce code." if code and not obj else "",
        }
        | teacher_context(request, "vehicle"),
    )
    response["Cache-Control"] = "private, no-store"
    response["Referrer-Policy"] = "no-referrer"
    return response


def vehicle_context(form):
    from .vehicles import GRADES, DEPARTEMENTS, DUREES

    filieres = list(
        dict.fromkeys(
            f"{cycle} {name}".strip()
            for cycle, name in EmploiDuTemps.objects.filter(publie=True).values_list(
                "cycle", "filiere"
            )
        )
    )
    filieres.append("Autre promotion / groupe de recherche")
    return {
        "form": form,
        "old": lambda name, default="": (
            form.data.get(name, default)
            if form.is_bound
            else form.initial.get(name, default)
        ),
        "grades": tuple(
            dict.fromkeys(
                GRADES
                + (
                    (form.initial["grade_professeur"],)
                    if form.initial.get("grade_professeur")
                    else ()
                )
            )
        ),
        "departements": tuple(
            dict.fromkeys(
                DEPARTEMENTS
                + (
                    (form.initial["departement"],)
                    if form.initial.get("departement")
                    else ()
                )
            )
        ),
        "durees": DUREES,
        "filieres": filieres,
        "today": timezone.localdate().isoformat(),
        "default_visit": (timezone.localdate() + timedelta(days=3)).isoformat(),
        "form_errors": (
            [str(error) for errors in form.errors.values() for error in errors]
            if form.is_bound
            else []
        ),
    }


@require_POST
def vehicule_mission_direct(request):
    # The legacy submission URL records a pending request, just like the form.
    return vehicule(request)


def _vehicle_pdf_response(request, obj, mission=False, download=None):
    from .pdf import vehicle_pdf, mission_pdf

    if mission and not obj.ordre_mission_disponible:
        response = HttpResponse(
            "L’ordre de mission sera téléchargeable uniquement après validation par l’administration.",
            status=403,
            content_type="text/plain; charset=utf-8",
        )
    else:
        response = HttpResponse(
            mission_pdf(obj) if mission else vehicle_pdf(obj),
            content_type="application/pdf",
        )
        download = request.GET.get("download") == "1" if download is None else download
        prefix = "Ordre_de_Mission" if mission else "Demande_Vehicule"
        response["Content-Disposition"] = (
            "attachment" if download else "inline"
        ) + f'; filename="{prefix}_{obj.code_suivi}.pdf"'
    response["Cache-Control"] = "private, no-store"
    response["Referrer-Policy"] = "no-referrer"
    return response


@teacher_required(allow_manager=True)
@require_GET
def vehicule_pdf(request, code):
    return _vehicle_pdf_response(
        request, get_object_or_404(visible_vehicles(request), code_suivi=code)
    )


@teacher_required(allow_manager=True)
@require_GET
def vehicule_mission_pdf(request, code):
    return _vehicle_pdf_response(
        request,
        get_object_or_404(visible_vehicles(request), code_suivi=code),
        mission=True,
    )


def visitor_stats(request):
    visitor = request.get_signed_cookie("est_visitor", default="", salt="est-visitor")
    count = (
        SiteVisitor.objects.filter(visitor_id=visitor)
        .values_list("consultations_count", flat=True)
        .first()
        or 0
    )
    return {
        "total_consultations": SiteVisit.objects.count(),
        "unique_visitors": SiteVisitor.objects.count(),
        "today_consultations": SiteVisit.objects.filter(
            visited_date=timezone.localdate()
        ).count(),
        "visitor_consultations": count,
    }


def stats_api(request):
    data = visitor_stats(request)
    return JsonResponse({"success": True, "data": data, **data})


def legacy_admin(request, section=""):
    models = {
        "publications": "publication",
        "professeurs": "professeur",
        "photos": "photo",
        "emplois-du-temps": "emploidutemps",
        "textes-reglements": "reglement",
    }
    if section in models:
        from .panel import panel_route

        key = {"emplois-du-temps": "emplois", "textes-reglements": "reglements"}.get(
            section, section
        )
        return redirect(panel_route("admin." + key + ".index"))
    return redirect("panel-dashboard")

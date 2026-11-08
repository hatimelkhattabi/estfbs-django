from functools import wraps
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from .models import Enseignant, DemandeVehicule


def teacher_profile(request):
    if not request.user.is_authenticated or not request.user.is_active:
        return None
    return (
        Enseignant.objects.select_related("utilisateur")
        .filter(utilisateur=request.user, actif=True)
        .first()
    )


def vehicle_manager(request):
    return (
        request.user.is_authenticated
        and request.user.is_active
        and request.user.is_staff
        and request.user.has_perm("portal.view_demandevehicule")
    )


def private(response):
    response["Cache-Control"] = "private, no-store"
    # Form navigation needs its same-origin Origin/Referer for Django CSRF.
    # Downloads can retain the stricter policy because they contain no forms.
    response["Referrer-Policy"] = (
        "same-origin"
        if response.get("Content-Type", "").startswith("text/html")
        else "no-referrer"
    )
    return response


def teacher_required(view=None, *, allow_manager=False, password_page=False):
    def decorate(fn):
        @wraps(fn)
        def wrapped(request, *args, **kwargs):
            profile = teacher_profile(request)
            request.enseignant = profile
            json_request = (
                "application/json" in request.headers.get("Accept", "")
                or request.content_type == "application/json"
            )
            if allow_manager and vehicle_manager(request):
                return private(fn(request, *args, **kwargs))
            if not request.user.is_authenticated:
                url = reverse("teacher-login")
                response = (
                    JsonResponse(
                        {
                            "success": False,
                            "message": "Connectez-vous à l’espace enseignants.",
                            "login_url": url,
                        },
                        status=401,
                    )
                    if json_request
                    else redirect_to_login(request.get_full_path(), url)
                )
                return private(response)
            if profile is None:
                return private(
                    HttpResponse(
                        "Ce compte n’a pas accès à l’espace enseignants.", status=403
                    )
                )
            if profile.changer_mot_de_passe and not password_page:
                url = reverse("teacher-password")
                response = (
                    JsonResponse(
                        {
                            "success": False,
                            "message": "Choisissez votre nouveau mot de passe.",
                            "password_url": url,
                        },
                        status=403,
                    )
                    if json_request
                    else redirect_to_login(request.get_full_path(), url)
                )
                return private(response)
            return private(fn(request, *args, **kwargs))

        return wrapped

    return decorate(view) if view is not None else decorate


def visible_vehicles(request):
    if vehicle_manager(request):
        return DemandeVehicule.objects.all()
    profile = getattr(request, "enseignant", None) or teacher_profile(request)
    if profile and not profile.changer_mot_de_passe:
        return DemandeVehicule.objects.filter(enseignant=profile)
    return DemandeVehicule.objects.none()


def teacher_context(request, active="home"):
    profile = getattr(request, "enseignant", None)
    return {
        "enseignant": profile,
        "active": active,
        "teacher_layout": (
            "enseignants/layout.html" if profile else "layouts/public.html"
        ),
    }

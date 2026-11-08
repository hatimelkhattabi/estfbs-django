import hashlib
import secrets
from django.conf import settings
from django.db import DatabaseError
from django.db.models import F
from django.utils import timezone


class VisitorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and request.path.startswith("/admin/login"):
            from .views import throttle

            if throttle(request, "admin-login", 6, 300):
                from django.http import HttpResponse

                return HttpResponse(
                    "Trop de tentatives. Réessayez dans cinq minutes.", status=429
                )
        response = self.get_response(request)
        if (
            request.method != "GET"
            or response.status_code != 200
            or request.path.startswith(
                (
                    "/admin",
                    "/espace-enseignant",
                    "/demande-vehicule",
                    "/professeur/demande-vehicule",
                    "/api/",
                    "/static/",
                    "/documents/",
                    "/medias/",
                    "/images/",
                    "/professeurs/",
                )
            )
            or request.path.endswith("/pdf")
        ):
            return response
        from .models import SiteVisitor, SiteVisit

        visitor = request.get_signed_cookie(
            "est_visitor", default="", salt="est-visitor"
        )
        if len(visitor) != 32:
            visitor = secrets.token_hex(16)
        ip_hash = hashlib.sha256(
            (settings.SECRET_KEY + request.META.get("REMOTE_ADDR", "")).encode()
        ).hexdigest()
        try:
            record, _ = SiteVisitor.objects.get_or_create(
                visitor_id=visitor, defaults={"ip_hash": ip_hash}
            )
            SiteVisitor.objects.filter(pk=record.pk).update(
                consultations_count=F("consultations_count") + 1,
                last_page=request.path[:255],
                last_visited_at=timezone.now(),
            )
            SiteVisit.objects.create(
                visitor_id=visitor, ip_hash=ip_hash, page_url=request.path[:255]
            )
            response.set_signed_cookie(
                "est_visitor",
                visitor,
                salt="est-visitor",
                max_age=31536000,
                httponly=True,
                samesite="Lax",
                secure=not settings.DEBUG,
            )
        except DatabaseError:
            pass
        return response

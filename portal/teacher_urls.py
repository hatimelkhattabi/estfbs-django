from django.urls import path
from . import teacher_views as t
from . import views as v
from . import teacher_services as s
from . import teacher_print_actions as a

urlpatterns = [
    path("", t.home, name="teacher-home"),
    path("connexion/", t.login, name="teacher-login"),
    path("deconnexion/", t.logout, name="teacher-logout"),
    path("mot-de-passe/", t.password, name="teacher-password"),
    path("message-anonyme/", t.anonymous, name="teacher-anonymous"),
    path("vehicule/", v.vehicule, name="teacher-vehicle"),
    path("impression/", t.printing, name="teacher-print"),
    path("documents-administratifs/", s.administrative, name="teacher-administrative"),
    path(
        "documents-administratifs/<uuid:reference>/",
        s.administrative_detail,
        name="teacher-administrative-detail",
    ),
    path(
        "documents-administratifs/<uuid:reference>/document/",
        s.administrative_file,
        name="teacher-administrative-file",
    ),
    path("listes-presence/", s.attendance, name="teacher-attendance"),
    path(
        "impressions/<uuid:reference>/documents/<int:document_id>/",
        t.print_file,
        name="teacher-print-document",
    ),
    path("mes-demandes/", t.requests, name="teacher-requests"),
    path("impressions/<uuid:reference>/", t.print_detail, name="teacher-print-detail"),
    path("impressions/<uuid:reference>/modifier/", a.edit, name="teacher-print-edit"),
    path(
        "impressions/<uuid:reference>/supprimer/", a.delete, name="teacher-print-delete"
    ),
    path(
        "impressions/<uuid:reference>/document/",
        t.print_file,
        name="teacher-print-file",
    ),
]

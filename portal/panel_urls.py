from django.urls import path, register_converter
from . import panel, teacher_admin as t


class ModuleConverter:
    regex = (
        "publications|professeurs|photos|emplois-du-temps|textes-reglements|etudiants"
    )

    def to_python(self, value):
        return {"emplois-du-temps": "emplois", "textes-reglements": "reglements"}.get(
            value, value
        )

    def to_url(self, value):
        return panel.SECTIONS.get(value, value)


register_converter(ModuleConverter, "panelmodule")
urlpatterns = [
    path(
        "documents-enseignants/",
        t.administrative_documents,
        name="teacher-admin-documents",
    ),
    path(
        "documents-enseignants/<uuid:reference>/",
        t.administrative_document_edit,
        name="teacher-admin-document-detail",
    ),
    path("comptes-enseignants/", t.accounts, name="teacher-admin-accounts"),
    path(
        "comptes-enseignants/ajouter/",
        t.account_edit,
        name="teacher-admin-account-create",
    ),
    path(
        "comptes-enseignants/importer/", t.accounts_import, name="teacher-admin-import"
    ),
    path(
        "comptes-enseignants/modele/", t.account_template, name="teacher-admin-template"
    ),
    path(
        "comptes-enseignants/<int:pk>/",
        t.account_edit,
        name="teacher-admin-account-edit",
    ),
    path("impressions/", t.prints, name="teacher-admin-prints"),
    path(
        "impressions/<uuid:reference>/", t.print_edit, name="teacher-admin-print-detail"
    ),
    path("messages-anonymes/", t.anonymous_messages, name="teacher-admin-messages"),
    path(
        "messages-anonymes/<int:pk>/",
        t.message_edit,
        name="teacher-admin-message-detail",
    ),
    path("", panel.dashboard, name="panel-dashboard"),
    path("login/", panel.login, name="panel-login"),
    path("logout/", panel.logout, name="panel-logout"),
    path("createur-images", panel.cover_creator, name="panel-cover-creator"),
    path("<panelmodule:module>", panel.listing, name="panel-index"),
    path("<panelmodule:module>/create", panel.editor, name="panel-create"),
    path("<panelmodule:module>/<int:pk>/edit", panel.editor, name="panel-edit"),
    path("<panelmodule:module>/<int:pk>/toggle", panel.toggle, name="panel-toggle"),
    path("<panelmodule:module>/<int:pk>/destroy", panel.destroy, name="panel-destroy"),
    path(
        "publications/<int:pk>/cover-assets/<str:kind>",
        panel.cover_asset,
        name="panel-cover-asset",
    ),
]

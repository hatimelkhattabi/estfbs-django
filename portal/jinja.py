import json
import string
from urllib.parse import urlencode
from jinja2 import Environment
from django.urls import reverse
from django.utils.formats import date_format
from .files import asset_url

ALIASES = {
    "home": "home",
    "presentation": "presentation",
    "publications.archive": "publications",
    "publications.show": "publication",
    "emplois.index": "emplois",
    "reglements.index": "reglements",
    "reglements.document": "reglement-document",
    "professeurs.index": "professeurs",
    "professeurs.show": "professeur",
    "professeurs.photo": "professeur-photo",
    "personnel.form": "personnel",
    "galerie.index": "galerie",
    "medias.file": "media-file",
    "medias.thumbnail": "media-thumbnail",
    "vehicule.form": "vehicule",
    "vehicule.store": "vehicule",
    "vehicule.status": "vehicule-status",
    "vehicule.pdf": "vehicule-pdf",
    "vehicule.ordre-mission.pdf": "vehicule-mission-pdf",
    "vehicule.ordre-mission.direct": "vehicule-mission-direct",
    "vehicule.suivi": "vehicule-suivi",
    "tracking": "tracking",
    "api.visitor-stats": "visitor-stats",
    "documents.show": "document",
    "admin.documents.store": "document-upload",
    "admin.dashboard": "admin:index",
    "login": "admin:login",
    "logout": "admin:logout",
}


def route(name, params=None, absolute=False):
    name = ALIASES.get(name, name)
    if params is None or params == []:
        return reverse(name)
    if isinstance(params, dict):
        path_keys = {
            "publication": "pk",
            "professeur": "pk",
            "reglement": "pk",
            "photo": "pk",
            "document": "uid",
            "code": "code",
            "pk": "pk",
            "uid": "uid",
            "reference": "reference",
            "document_id": "document_id",
        }
        args = {
            path_keys[k]: (v.pk if hasattr(v, "pk") else v)
            for k, v in params.items()
            if k in path_keys
        }
        query = {k: v for k, v in params.items() if k not in path_keys}
        return reverse(name, kwargs=args) + ("?" + urlencode(query) if query else "")
    return reverse(name, args=[params.pk if hasattr(params, "pk") else params])


def url(value):
    if value.startswith(("http://", "https://")):
        return value
    value = value.lstrip("/")
    if value.startswith("index.html"):
        value = value[len("index.html") :]
    return "/" + value


def config_value(key, default=None):
    from .context import formations

    data = {"formations_navigation": formations()}
    for part in key.split("."):
        if not isinstance(data, dict) or part not in data:
            return default
        data = data[part]
    return data


def fmt_date(value, fmt="d/m/Y"):
    if not value:
        return ""
    return date_format(value, fmt)


def environment(**options):
    env = Environment(**options)
    env.globals.update(
        asset=asset_url,
        url=url,
        route=route,
        config=config_value,
        len=len,
        range=range,
        fmt_date=fmt_date,
        alphabet=string.ascii_uppercase,
        number_format=lambda n, *args: f"{int(n):,}".replace(",", " "),
    )
    env.filters["date_fr"] = fmt_date
    return env

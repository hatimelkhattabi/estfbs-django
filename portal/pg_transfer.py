"""Métadonnées et contrôles communs de l’export/import PostgreSQL."""

import hashlib
from django.apps import apps
from django.core.management.base import CommandError

EXCLUDED = ["contenttypes.contenttype", "auth.permission", "sessions.session"]


def transferable_models():
    return [
        model
        for model in apps.get_models()
        if model._meta.managed
        and not model._meta.proxy
        and model._meta.label_lower not in EXCLUDED
    ]


def counts():
    return {
        model._meta.label_lower: model._base_manager.count()
        for model in transferable_models()
    }


def file_digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_manifest(value):
    if (
        not isinstance(value, dict)
        or value.get("format") != "estfbs-postgresql-v1"
        or value.get("fixture") != "data.json"
    ):
        raise CommandError("Dossier de transfert invalide : manifest.json non reconnu.")
    expected = value.get("counts")
    labels = {model._meta.label_lower for model in transferable_models()}
    if (
        not isinstance(expected, dict)
        or set(expected) != labels
        or any(type(v) is not int or v < 0 for v in expected.values())
    ):
        raise CommandError(
            "Les modèles ou les comptages ne correspondent pas à cette version du projet."
        )
    return expected

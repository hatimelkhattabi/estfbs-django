import re
from urllib.parse import urlsplit
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

validate_apogee = RegexValidator(
    regex=r"\A[0-9]{1,32}\Z",
    message="Le numéro Apogée doit contenir uniquement des chiffres (32 maximum).",
    code="invalid_apogee",
)


def valid_link(value):
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 2000
        or re.search(r"[\x00-\x20\x7f\\]", value)
    ):
        return False
    if value.startswith("/"):
        return not value.startswith("//")
    try:
        p = urlsplit(value)
        return (
            p.scheme.lower() in ("http", "https")
            and bool(p.hostname)
            and not p.username
            and not p.password
        )
    except ValueError:
        return False


def validate_document_link(value):
    if value and not valid_link(value):
        raise ValidationError(
            "Utilisez un lien HTTP/HTTPS ou un chemin local commençant par /."
        )

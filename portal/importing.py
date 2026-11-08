import json
from datetime import datetime, date
from zoneinfo import ZoneInfo
from django.db import models, transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
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

TABLES = {
    "actualites_evenements": Publication,
    "professeurs": Professeur,
    "photos": Photo,
    "emplois_du_temps": EmploiDuTemps,
    "reglements": Reglement,
    "uploaded_documents": UploadedDocument,
    "demandes_etudiants": DemandeEtudiant,
    "demandes_personnel": DemandePersonnel,
    "messages_contact": MessageContact,
    "demandes_vehicule": DemandeVehicule,
    "site_visitors": SiteVisitor,
    "site_visits": SiteVisit,
}


def converted(field, value, source_zone="UTC"):
    if isinstance(field, models.JSONField):
        for _ in range(2):
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except ValueError:
                    return None
        return value
    if value is None:
        if field.null:
            return None
        if isinstance(field, (models.CharField, models.TextField)):
            return ""
        if field.has_default():
            return field.get_default()
        return None
    if isinstance(field, models.DateTimeField):
        if isinstance(value, str):
            value = parse_datetime(value)
        if value is None:
            return field.get_default() if field.has_default() else None
        return (
            timezone.make_aware(value, ZoneInfo(source_zone))
            if timezone.is_naive(value)
            else value
        )
    if isinstance(field, models.DateField):
        return parse_date(value) if isinstance(value, str) else value
    if isinstance(field, models.BooleanField):
        return value not in (False, 0, "0", "false", "False", "")
    if isinstance(field, models.IntegerField):
        return int(value)
    return value


@transaction.atomic
def import_rows(data, empty_only=False, source_zone="UTC"):
    results = {}
    for table, model in TABLES.items():
        rows = data.get(table, [])
        if empty_only and model.objects.exists():
            continue
        count = 0
        for row in rows:
            values = {}
            for field in model._meta.concrete_fields:
                if field.name == "created_by":
                    continue
                if field.name in row:
                    values[field.name] = converted(field, row[field.name], source_zone)
            pk = values.pop("id", None)
            if table == "actualites_evenements":
                values.setdefault(
                    "date_publication", values.get("date_creation", timezone.now())
                )
                if not values.get("date_publication"):
                    values["date_publication"] = timezone.now()
            if pk is not None:
                model.objects.update_or_create(pk=pk, defaults=values)
            else:
                model.objects.create(**values)
            count += 1
        results[table] = count
    # Reset integer sequences after explicit IDs, on SQLite, MySQL or PostgreSQL.
    from django.db import connection
    from django.core.management.color import no_style

    statements = connection.ops.sequence_reset_sql(no_style(), list(TABLES.values()))
    with connection.cursor() as cursor:
        for sql in statements:
            cursor.execute(sql)
    return results

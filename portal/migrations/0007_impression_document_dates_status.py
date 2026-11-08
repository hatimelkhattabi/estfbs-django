from django.db import migrations, models


def preserve_dates_and_statuses(apps, schema_editor):
    Request = apps.get_model("portal", "DemandeImpression")
    Document = apps.get_model("portal", "DocumentImpression")
    alias = schema_editor.connection.alias
    documents = (
        Document.objects.using(alias)
        .filter(date_souhaitee__isnull=True)
        .select_related("demande")
    )
    batch = []
    for document in documents.iterator(chunk_size=500):
        document.date_souhaitee = document.demande.date_souhaitee
        batch.append(document)
        if len(batch) == 500:
            Document.objects.using(alias).bulk_update(batch, ["date_souhaitee"])
            batch = []
    if batch:
        Document.objects.using(alias).bulk_update(batch, ["date_souhaitee"])
    for old, new in [
        ("Acceptée", "Vue"),
        ("En cours", "Vue"),
        ("Prête à récupérer", "Terminée"),
    ]:
        Request.objects.using(alias).filter(statut=old).update(statut=new)
    # A refused print was seen, but must never be presented as completed.
    for request in (
        Request.objects.using(alias).filter(statut="Refusée").iterator(chunk_size=500)
    ):
        note = "Ancien statut avant mise à jour : Refusée."
        reply = note + (
            "\n" + request.reponse_administration
            if request.reponse_administration
            else ""
        )
        Request.objects.using(alias).filter(pk=request.pk).update(
            statut="Vue", reponse_administration=reply
        )


class Migration(migrations.Migration):
    dependencies = [("portal", "0006_services_enseignants")]
    operations = [
        migrations.AddField(
            model_name="documentimpression",
            name="date_souhaitee",
            field=models.DateField(null=True, verbose_name="document prêt pour le"),
        ),
        migrations.RunPython(preserve_dates_and_statuses, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="documentimpression",
            name="date_souhaitee",
            field=models.DateField(verbose_name="document prêt pour le"),
        ),
        migrations.AlterField(
            model_name="demandeimpression",
            name="statut",
            field=models.CharField(
                max_length=30,
                default="En attente",
                choices=[
                    ("En attente", "En attente"),
                    ("Vue", "Vue"),
                    ("Terminée", "Terminée"),
                ],
            ),
        ),
    ]

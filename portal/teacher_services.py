"""Administrative requests and presence lists for authenticated teachers."""

from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_GET, require_http_methods
from .models import DemandeDocumentAdministratif, Etudiant
from .teacher_forms import AdministrativeDocumentForm, AttendanceForm, cohort_values
from .attendance_cohorts import year_number
from .attendance_excel import attendance_sources, source_for, source_students
from .teacher_access import teacher_required, private
from .teacher_views import page
from .views import throttle
from .files import file_response


@teacher_required
@require_http_methods(["GET", "POST"])
def administrative(request):
    form = AdministrativeDocumentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if throttle(request, "admin-doc:" + str(request.enseignant.pk), 10, 3600):
            form.add_error(None, "Limite d’envoi atteinte. Réessayez plus tard.")
        else:
            obj = form.save(commit=False)
            obj.enseignant = request.enseignant
            obj.save()
            messages.success(
                request, "Votre demande de document a été envoyée à l’administration."
            )
            return redirect("teacher-administrative-detail", reference=obj.reference)
    return page(
        request,
        "administrative.html",
        active="administrative",
        form=form,
        page_title="Documents administratifs",
        description="Choisissez le document souhaité. L’administration le prépare et vous informe ici lorsqu’il est prêt.",
    )


@teacher_required
@require_GET
def administrative_detail(request, reference):
    obj = get_object_or_404(
        DemandeDocumentAdministratif, reference=reference, enseignant=request.enseignant
    )
    return page(
        request,
        "administrative_detail.html",
        active="administrative",
        item=obj,
        page_title="Ma demande de document",
    )


def _document_response(request, reference, manager=False):
    qs = DemandeDocumentAdministratif.objects.all()
    if not manager:
        qs = qs.filter(enseignant=request.enseignant, statut="Prête").exclude(
            document=""
        )
    obj = get_object_or_404(qs, reference=reference)
    return private(
        file_response(
            obj.document,
            filename=obj.nom_document,
            mime="application/pdf",
            download=True,
            request=request,
        )
    )


@require_GET
def administrative_file(request, reference):
    user = request.user
    if (
        user.is_authenticated
        and user.is_active
        and user.is_staff
        and user.has_perm("portal.view_demandedocumentadministratif")
    ):
        return _document_response(request, reference, manager=True)
    return _teacher_administrative_file(request, reference)


@teacher_required
@require_GET
def _teacher_administrative_file(request, reference):
    return _document_response(request, reference)


def cohort_filter(field, value):
    # The student importer joins multiple memberships with ' / '. Match whole values.
    return (
        Q(**{field: value})
        | Q(**{field + "__startswith": value + " / "})
        | Q(**{field + "__endswith": " / " + value})
        | Q(**{field + "__contains": " / " + value + " / "})
    )


@teacher_required
@require_GET
def attendance(request):
    sources = attendance_sources()
    form = AttendanceForm(request.GET if request.GET else None)
    students, count = [], 0
    selected_source = None
    if form.is_bound and form.is_valid():
        if sources:
            selected_source = source_for(form.cleaned_data)
            selected_students = (
                source_students(selected_source) if selected_source else []
            )
            count = len(selected_students)
        else:
            qs = Etudiant.objects.filter(actif=True)
            for field in ("filiere", "annee_universitaire"):
                qs = qs.filter(cohort_filter(field, form.cleaned_data[field]))
            levels = Q(pk__in=[])
            for value in cohort_values("niveau"):
                if year_number(value) == form.cleaned_data["niveau"]:
                    levels |= cohort_filter("niveau", value)
            qs = qs.filter(levels)
            count = qs.count()
            selected_students = qs
        if count > 2000:
            form.add_error(
                None,
                "La sélection dépasse 2 000 étudiants. Vérifiez la classe choisie.",
            )
        elif request.GET.get("format") == "pdf" and count:
            if selected_source:
                from .attendance_excel_pdf import excel_presence_pdf

                pdf = excel_presence_pdf(selected_source, request.enseignant)
            else:
                from .attendance_pdf import attendance_pdf

                pdf = attendance_pdf(
                    list(selected_students), form.cleaned_data, request.enseignant
                )
            response = HttpResponse(pdf, content_type="application/pdf")
            response["Content-Disposition"] = (
                'attachment; filename="Liste-presence-EST-FBS.pdf"'
            )
            return private(response)
        else:
            students = list(selected_students[:50])
    values = (
        {key: form.data.get(key, "") for key in form.fields} if form.is_bound else {}
    )
    from urllib.parse import urlencode

    return page(
        request,
        "attendance.html",
        active="attendance",
        form=form,
        students=students,
        student_count=count,
        pdf_query=urlencode(dict(values, format="pdf")),
        page_title="Listes de présence",
        description="Choisissez la filière, l’année d’études et l’année universitaire, puis téléchargez la liste prête à signer.",
        has_students=bool(sources) or Etudiant.objects.filter(actif=True).exists(),
        excel_sources=bool(sources),
    )

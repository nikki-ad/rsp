from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from assignments.models import Assignment
from assignments.views import download_assignment_file
from language_unit.models import LanguageAssignment, LanguageMaterial
from language_unit.views import download_language_assignment, download_language_material
from materials.models import EducationalMaterial
from materials.views import download_material
from reports.models import StudentReportCard
from reports.views import download_report_card


MEDIA_DIRECTORIES = {
    "assignments": (Assignment, download_assignment_file, ("file", "image", "video")),
    "educational_materials": (EducationalMaterial, download_material, ("file",)),
    "language_assignments": (LanguageAssignment, download_language_assignment, ("file", "image", "video")),
    "language_materials": (LanguageMaterial, download_language_material, ("file",)),
    "report_cards": (StudentReportCard, download_report_card, ("file",)),
}


@login_required
@require_safe
@never_cache
def protected_media(request, directory, filename):
    model, download, fields = MEDIA_DIRECTORIES[directory]
    name = f"{directory}/{filename}"
    field = "file"
    if filename.startswith("images/") and "image" in fields:
        field = "image"
    elif filename.startswith("videos/") and "video" in fields:
        field = "video"
    # A file path can be shared by multiple records. Fail closed in that case.
    matches = list(model.objects.filter(**{field: name}).values_list("pk", flat=True)[:2])
    if len(matches) != 1:
        raise Http404()
    if len(fields) == 1:
        return download(request, matches[0])
    return download(request, matches[0], field)

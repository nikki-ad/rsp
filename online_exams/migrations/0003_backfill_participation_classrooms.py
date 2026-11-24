from collections import defaultdict

from django.db import migrations


def backfill_classrooms(apps, schema_editor):
    db = schema_editor.connection.alias
    Participation = apps.get_model("online_exams", "Participation")
    Enrollment = apps.get_model("academic", "Enrollment")
    LanguageGroup = apps.get_model("language_unit", "LanguageGroup")

    enrollments = defaultdict(list)
    for student, classroom, name, grade, created in Enrollment.objects.using(db).values_list(
        "student_id", "classroom_id", "classroom__name", "classroom__grade__title", "created_at"
    ).iterator():
        enrollments[(student, f"{grade} {name}")].append((classroom, created))

    # The old form marked the same student across all groups and stored the first
    # label. A student also enrolled in language could have been selected there.
    language_students = set(LanguageGroup.objects.using(db).exclude(
        students__isnull=True
    ).values_list("students", flat=True))
    pending = []
    old_rows = Participation.objects.using(db).filter(
        classroom__isnull=True
    ).exclude(classroom_label="").exclude(classroom_label__startswith="زبان: ")
    for row in old_rows.only("student_id", "classroom_label", "created_at").iterator(chunk_size=500):
        if row.student_id in language_students:
            continue
        matches = {
            classroom for classroom, created in enrollments[(row.student_id, row.classroom_label)]
            if created <= row.created_at
        }
        if len(matches) == 1:
            row.classroom_id = matches.pop()
            pending.append(row)
        if len(pending) == 500:
            Participation.objects.using(db).bulk_update(pending, ["classroom"])
            pending.clear()
    if pending:
        Participation.objects.using(db).bulk_update(pending, ["classroom"])


class Migration(migrations.Migration):
    dependencies = [
        ("online_exams", "0002_participation_classroom"),
        ("language_unit", "0004_languageassignmentsubmission_feedback_file_and_more"),
    ]
    operations = [migrations.RunPython(backfill_classrooms, migrations.RunPython.noop)]

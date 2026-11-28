from accounts.choices import Role
from accounts.models import StudentProfile
from accounts.permissions import is_school_admin, is_language_teacher
from academic.models import Classroom, Enrollment
from language_unit.models import LanguageGroup
from .models import Exam


MANAGEMENT_ROLES = {Role.TEACHER, Role.OPERATOR, Role.FINANCE,
                    Role.SCHOOL_MANAGER, Role.SUPER_ADMIN}


def can_manage(user):
    return user.is_authenticated and (user.is_superuser or user.role in MANAGEMENT_ROLES)


def managed_exams(user):
    if not can_manage(user):
        return Exam.objects.none()
    return Exam.objects.all() if is_school_admin(user) else Exam.objects.filter(created_by=user)


def participant_groups(user):
    classrooms = Classroom.objects.filter(academic_year__status="active")
    languages = LanguageGroup.objects.filter(is_active=True, academic_year__status="active")
    if user.role == Role.TEACHER and not is_school_admin(user):
        teacher = getattr(user, "teacher_profile", None)
        classrooms = (classrooms.none() if not teacher or is_language_teacher(user)
                      else classrooms.filter(teacher_assignments__teacher=teacher))
        languages = languages.filter(teachers=teacher) if teacher else languages.none()
    groups = []
    for classroom in classrooms.select_related("grade").prefetch_related("enrollments__student__user").distinct():
        students = [e.student for e in classroom.enrollments.all() if e.is_active]
        groups.append({"label": str(classroom), "students": students})
    for group in languages.prefetch_related("students__user").distinct():
        groups.append({"label": "زبان: " + group.title, "students": list(group.students.all())})
    for group in groups:
        group["students"].sort(key=lambda s: (s.user.last_name, s.user.first_name))
    return groups


def eligible_students(user):
    ids = {s.pk for group in participant_groups(user) for s in group["students"]}
    return StudentProfile.objects.filter(pk__in=ids).select_related("user")

from decimal import Decimal, ROUND_HALF_UP
from functools import partial
import logging

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
from activitylog.models import ActivityLog
from .models import Exam, Participation, Question

logger = logging.getLogger(__name__)


def score(answers, key, negative):
    correct = sum(answers.get(str(number)) == value for number, value in key.items())
    wrong = sum(answers.get(str(number)) in (1, 2, 3, 4) and
                answers.get(str(number)) != value for number, value in key.items())
    blank = len(key) - correct - wrong
    points = Decimal(correct) - (Decimal(wrong) / 3 if negative else 0)
    percentage = (points * 100 / len(key)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return correct, wrong, blank, percentage


@transaction.atomic
def publish(exam_id, user):
    exam = Exam.objects.select_for_update().get(pk=exam_id)
    questions = list(exam.questions.all())
    if exam.published:
        return exam
    if exam.closes_at <= timezone.now():
        raise ValidationError("زمان پایان آزمون گذشته است.")
    if not exam.participations.exists():
        raise ValidationError("شرکت‌کنندگان را انتخاب کنید.")
    if len(questions) != exam.question_count or any(q.correct_option not in (1, 2, 3, 4) for q in questions):
        raise ValidationError("تعداد سؤال‌ها یا کلید کامل نیست.")
    if exam.mode == "pdf" and not exam.question_pdf:
        raise ValidationError("فایل سؤال‌ها ثبت نشده است.")
    if exam.mode == "typed" and any(not q.text.strip() or len(q.options) != 4 or
                                    any(not str(o).strip() for o in q.options) for q in questions):
        raise ValidationError("متن سؤال‌ها و هر چهار گزینه باید کامل باشد.")
    exam.published = True
    exam.save(update_fields=["published", "updated_at"])
    ActivityLog.objects.create(user=user, action="انتشار آزمون آنلاین", description=exam.title)
    return exam


def _finish(participation, now):
    """Caller holds exam and participation locks, always in that order."""
    if participation.submitted_at or participation.result_deleted:
        return
    key = dict(participation.exam.questions.values_list("number", "correct_option"))
    participation.correct, participation.wrong, participation.blank, participation.percentage = score(
        participation.answers, key, participation.exam.negative_marking)
    participation.submitted_at = min(now, participation.deadline_at)
    participation.save(update_fields=["correct", "wrong", "blank", "percentage", "submitted_at", "updated_at"])
    transaction.on_commit(partial(ensure_report, participation.pk), robust=True)


def ensure_report(participation_id):
    from .reports import write_report
    # Same lock order as purge/finalize: deletion cannot race with generation.
    exam_id = Participation.objects.filter(pk=participation_id).values_list("exam_id", flat=True).first()
    if exam_id is None:
        return
    with transaction.atomic():
        exam = Exam.objects.select_for_update().filter(pk=exam_id).first()
        if exam is None:
            return
        participation = Participation.objects.select_for_update().select_related("student__user").get(pk=participation_id)
        participation.exam = exam
        if (not participation.submitted_at or participation.result_deleted or exam.results_deleted or
                exam.report_files_deleted or participation.report):
            return
        write_report(participation)


@transaction.atomic
def start(exam_id, student):
    exam = Exam.objects.select_for_update().filter(pk=exam_id).first()
    if exam is None:
        raise ValidationError("آزمون حذف شده است.")
    p = Participation.objects.select_for_update().get(exam=exam, student=student)
    now = timezone.now()
    p.exam = exam
    if p.result_deleted or exam.results_deleted:
        raise ValidationError("نتایج این آزمون حذف شده است؛ شرکت دوباره ممکن نیست.")
    if p.started_at:
        if not p.submitted_at and now >= p.deadline_at:
            _finish(p, now)
        return p
    if not exam.published or now < exam.opens_at or now >= exam.closes_at:
        raise ValidationError("اکنون امکان شروع این آزمون وجود ندارد.")
    p.started_at = now
    p.deadline_at = exam.deadline(now)
    p.save(update_fields=["started_at", "deadline_at", "updated_at"])
    return p


@transaction.atomic
def record(participation_id, *, number=None, choice=None, submit=False):
    exam_id = Participation.objects.filter(pk=participation_id).values_list("exam_id", flat=True).first()
    if exam_id is None:
        raise ValidationError("آزمون حذف شده است.")
    exam = Exam.objects.select_for_update().filter(pk=exam_id).first()
    if exam is None:
        raise ValidationError("آزمون حذف شده است.")
    p = Participation.objects.select_for_update().get(pk=participation_id)
    p.exam = exam
    now = timezone.now()
    if p.result_deleted or exam.results_deleted or not p.started_at:
        raise ValidationError("پاسخ‌نامه قابل تغییر نیست.")
    if p.submitted_at:
        return p, False
    if now >= p.deadline_at:
        _finish(p, now)
        return p, False
    if number is not None:
        if type(number) is not int or not 1 <= number <= exam.question_count:
            raise ValidationError("شماره سؤال معتبر نیست.")
        if choice is not None and (type(choice) is not int or choice not in (1, 2, 3, 4)):
            raise ValidationError("گزینه معتبر نیست.")
        if choice is None:
            p.answers.pop(str(number), None)
        else:
            p.answers[str(number)] = choice
        p.save(update_fields=["answers", "updated_at"])
    if submit:
        _finish(p, now)
    return p, True


def finalize_due(exam_id=None):
    due = Participation.objects.filter(started_at__isnull=False, submitted_at__isnull=True,
        result_deleted=False, deadline_at__lte=timezone.now())
    if exam_id:
        due = due.filter(exam_id=exam_id)
    count = 0
    for pk in due.values_list("pk", flat=True).iterator(chunk_size=100):
        try:
            record(pk)
        except ValidationError:
            if Participation.objects.filter(pk=pk).exists():
                raise
            continue
        count += 1
    return count


@transaction.atomic
def purge(exam_id, user, *, full=False):
    from accounts.permissions import is_school_admin
    from django.core.exceptions import PermissionDenied
    if not is_school_admin(user):
        raise PermissionDenied
    exam = Exam.objects.select_for_update().get(pk=exam_id)
    if timezone.now() < exam.closes_at:
        raise ValidationError("حذف پس از پایان بازه آزمون ممکن است.")
    exam.report_files_deleted = True
    if full:
        exam.results_deleted = True
    exam.save(update_fields=["report_files_deleted", "results_deleted", "updated_at"])
    # Files are private. Delete before clearing references: on failure references
    # remain so the operation can be retried; never silently orphan student files.
    for p in exam.participations.select_for_update():
        if p.report:
            p.report.delete(save=False)
        p.report = ""
        if full:
            p.answers = {}
            p.correct = p.wrong = p.blank = p.percentage = None
            p.result_deleted = True
        p.save()
    ActivityLog.objects.create(user=user, action="حذف کامل نتایج آزمون" if full else "حذف فایل‌های کارنامه آزمون", description=exam.title)


@transaction.atomic
def reopen(exam_id, user):
    """Share the exam lock with student start and publication."""
    from .access import managed_exams
    exam = get_object_or_404(managed_exams(user).select_for_update(), pk=exam_id)
    if exam.participations.filter(started_at__isnull=False).exists():
        raise ValidationError("دانش‌آموزی آزمون را شروع کرده است؛ ویرایش سؤال‌ها و زمان‌ها ممکن نیست.")
    if exam.results_deleted or exam.report_files_deleted:
        raise ValidationError("آزمون دارای نتایج حذف‌شده قابل بازگشت به پیش‌نویس نیست.")
    if exam.published:
        exam.published = False
        exam.save(update_fields=["published", "updated_at"])
        ActivityLog.objects.create(user=user, action="بازگشت آزمون به پیش‌نویس", description=exam.title)
    return exam


def _delete_exam_files(files):
    for storage, name in files:
        try:
            storage.delete(name)
        except OSError:
            logger.exception("Could not remove private file for deleted exam: %s", name)


@transaction.atomic
def delete_exam(exam_id, user):
    from accounts.permissions import is_school_admin
    from .access import managed_exams
    exam = get_object_or_404(managed_exams(user).select_for_update(), pk=exam_id)
    started = exam.participations.filter(started_at__isnull=False).exists()
    if started and not is_school_admin(user):
        raise PermissionDenied
    if started and timezone.now() < exam.closes_at:
        raise ValidationError("حذف آزمون دارای پاسخ فقط پس از پایان مهلت آزمون ممکن است.")
    files = [(p.report.storage, p.report.name) for p in exam.participations.all() if p.report]
    if exam.question_pdf:
        files.append((exam.question_pdf.storage, exam.question_pdf.name))
    title = exam.title
    exam.delete()
    ActivityLog.objects.create(user=user, action="حذف آزمون آنلاین", description=title)
    transaction.on_commit(partial(_delete_exam_files, files), robust=True)

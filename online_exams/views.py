import json
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from accounts.permissions import is_school_admin
from .access import can_manage, managed_exams, participant_groups
from .forms import ExamForm, KeyForm, QuestionForm
from .formatting import render_text
from .models import Exam, Participation, Question
from . import services


def _exam(user, pk):
    return get_object_or_404(managed_exams(user), pk=pk)


def _participation(user, pk):
    student = getattr(user, "student_profile", None)
    if user.role != "student" or not student:
        raise PermissionDenied
    return get_object_or_404(Participation.objects.select_related("exam", "student__user"),
                            exam_id=pk, student=student, exam__published=True)


def _error(request, error):
    messages.error(request, " ".join(error.messages))


def _private(response):
    response["Cache-Control"] = "no-store, private"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "sandbox"
    return response


@login_required
@never_cache
def index(request):
    manage = can_manage(request.user)
    if manage:
        page = Paginator(managed_exams(request.user).annotate(has_started=Exists(
            Participation.objects.filter(exam_id=OuterRef("pk"), started_at__isnull=False))), 30).get_page(request.GET.get("page"))
        exams = page
        rows = None
    else:
        if request.user.role != "student":
            raise PermissionDenied
        page = Paginator(Participation.objects.filter(student__user=request.user, exam__published=True)
                         .select_related("exam").order_by("-exam__created_at"), 30).get_page(request.GET.get("page"))
        rows = page
        exams = None
    return render(request, "online_exams/index.html", {"manage": manage, "exams": exams,
        "rows": rows, "page": page, "now": timezone.now(), "admin": is_school_admin(request.user)})


@login_required
@never_cache
def create(request, pk=None):
    if not can_manage(request.user):
        raise PermissionDenied
    existing = _exam(request.user, pk) if pk else None
    if existing and existing.published:
        raise PermissionDenied
    groups = participant_groups(request.user)
    initial = {"students": list(existing.participations.values_list("student_id", flat=True))} if existing else {}
    form = ExamForm(request.POST or None, request.FILES or None, user=request.user, instance=existing, initial=initial)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            if existing:
                locked = Exam.objects.select_for_update().get(pk=existing.pk)
                if locked.published:
                    raise PermissionDenied
            exam = form.save(commit=False)
            if not existing:
                exam.created_by = request.user
            exam.save()
            labels = {}
            for group in groups:
                for student in group["students"]:
                    labels.setdefault(student.pk, group["label"])
            if existing:
                exam.participations.all().delete()
            Participation.objects.bulk_create([Participation(exam=exam, student=student,
                classroom_label=labels.get(student.pk, ""), created_by=request.user)
                for student in form.cleaned_data["students"]])
            exam.questions.filter(number__gt=exam.question_count).delete()
            known = set(exam.questions.values_list("number", flat=True))
            Question.objects.bulk_create([Question(exam=exam, number=i)
                for i in range(1, exam.question_count + 1) if i not in known])
        return redirect("exam_questions" if exam.mode == "typed" else "exam_key", pk=exam.pk)
    selected = set(request.POST.getlist("students")) if request.method == "POST" else {
        str(value) for value in initial.get("students", [])}
    return render(request, "online_exams/create.html", {"form": form, "groups": groups, "selected": selected})


@login_required
@never_cache
def questions(request, pk):
    exam = _exam(request.user, pk)
    if exam.published or exam.mode != "typed":
        return redirect("exam_detail", pk=pk)
    try:
        number = int(request.GET.get("number", 1))
    except ValueError:
        number = 1
    question = get_object_or_404(Question, exam=exam, number=number)
    form = QuestionForm(request.POST or None, instance=question)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            locked = Exam.objects.select_for_update().get(pk=exam.pk)
            if locked.published:
                raise PermissionDenied
            form.save()
        if number < exam.question_count and request.POST.get("action") == "next":
            return redirect(f"{request.path}?number={number + 1}")
        return redirect("exam_key", pk=pk)
    return render(request, "online_exams/questions.html", {"exam": exam, "form": form,
        "question": question, "questions": exam.questions.all()})


@login_required
@never_cache
def key(request, pk):
    exam = _exam(request.user, pk)
    if exam.published:
        return redirect("exam_detail", pk=pk)
    questions = list(exam.questions.all())
    form = KeyForm(request.POST or None, questions=questions)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            locked = Exam.objects.select_for_update().get(pk=pk)
            if locked.published:
                raise PermissionDenied
            for question in questions:
                question.correct_option = form.cleaned_data[f"key_{question.number}"]
            Question.objects.bulk_update(questions, ["correct_option"])
        return redirect("exam_detail", pk=pk)
    return render(request, "online_exams/key.html", {"exam": exam, "form": form})


@login_required
@never_cache
def detail(request, pk):
    exam = _exam(request.user, pk)
    services.finalize_due(exam.pk)
    rows = list(exam.participations.select_related("student__user"))
    return render(request, "online_exams/detail.html", {"exam": exam, "rows": rows,
        "questions": exam.questions.all(), "now": timezone.now(), "admin": is_school_admin(request.user),
        "has_started": any(p.started_at for p in rows)})


@login_required
@require_POST
def publish(request, pk):
    exam = _exam(request.user, pk)
    try:
        services.publish(exam.pk, request.user)
        messages.success(request, "آزمون منتشر شد. تا پیش از شروع اولین دانش‌آموز، بازگشت به پیش‌نویس برای ویرایش ممکن است.")
    except ValidationError as error:
        _error(request, error)
    return redirect("exam_detail", pk=pk)


@login_required
@never_cache
def take(request, pk):
    p = _participation(request.user, pk)
    if p.started_at and not p.result_deleted:
        p, _ = services.record(p.pk)
    if p.submitted_at or p.result_deleted or p.exam.results_deleted:
        return redirect("exam_result", pk=pk)
    if request.method == "POST":
        try:
            p = services.start(pk, p.student)
            return redirect("exam_take", pk=pk)
        except ValidationError as error:
            _error(request, error)
    questions = []
    if p.started_at:
        # Do not serialize the key or any model object into exam HTML/JSON.
        questions = [{"number": q.number, "text": q.text, "options": q.options,
                      "answer": p.answers.get(str(q.number))} for q in p.exam.questions.all()]
    return render(request, "online_exams/take.html", {"p": p, "exam": p.exam,
        "questions": questions, "now": timezone.now(),
        "config": {"deadline": p.deadline_at.isoformat() if p.deadline_at else None,
                   "serverNow": timezone.now().isoformat(), "participation": str(p.pk)}})


@login_required
@require_POST
@never_cache
def answer(request, pk):
    p = _participation(request.user, pk)
    try:
        if len(request.body) > 2048:
            return JsonResponse({"error": "درخواست بیش از حد بزرگ است."}, status=400)
        data = json.loads(request.body)
        if not isinstance(data, dict) or data.get("number") is None:
            raise ValueError
        p, accepted = services.record(p.pk, number=data["number"], choice=data.get("choice"))
        return JsonResponse({"saved": accepted, "finished": bool(p.submitted_at),
            "serverNow": timezone.now().isoformat()})
    except (ValueError, KeyError, UnicodeDecodeError, ValidationError) as error:
        return JsonResponse({"error": " ".join(error.messages) if isinstance(error, ValidationError)
                             else "درخواست معتبر نیست."}, status=400)


@login_required
@require_POST
def submit(request, pk):
    p = _participation(request.user, pk)
    try:
        services.record(p.pk, submit=True)
    except ValidationError as error:
        _error(request, error)
    return redirect("exam_result", pk=pk)


@login_required
@never_cache
def result(request, pk):
    p = _participation(request.user, pk)
    if not p.result_deleted and p.started_at:
        p, _ = services.record(p.pk)
    if not p.result_deleted and not p.submitted_at and not p.exam.results_deleted:
        return redirect("exam_take", pk=pk)
    show_key = p.exam.show_key_immediately or timezone.now() >= p.exam.closes_at
    rows = []
    if not p.result_deleted:
        for q in p.exam.questions.all():
            value = p.answers.get(str(q.number))
            rows.append({"question": q, "answer": value, "status": "سفید" if value is None else
                         "درست" if value == q.correct_option else "غلط"})
    return render(request, "online_exams/result.html", {"p": p, "rows": rows, "show_key": show_key})


@login_required
@never_cache
def pdf(request, pk):
    exam = managed_exams(request.user).filter(pk=pk).first()
    if not exam:
        p = _participation(request.user, pk)
        if not p.started_at or p.result_deleted or timezone.now() >= p.deadline_at or p.submitted_at:
            raise PermissionDenied
        exam = p.exam
    if exam.mode != "pdf" or not exam.question_pdf:
        raise PermissionDenied
    return _private(FileResponse(exam.question_pdf.open("rb"), as_attachment=True,
                                 filename="questions.pdf", content_type="application/pdf"))


@login_required
@never_cache
def report(request, pk, participant_id):
    exam = _exam(request.user, pk)
    services.finalize_due(exam.pk)
    p = get_object_or_404(Participation, pk=participant_id, exam=exam, submitted_at__isnull=False,
                          result_deleted=False)
    # Deleting files is persistent: download must never regenerate them.
    if exam.report_files_deleted or not p.report:
        return HttpResponse("فایل کارنامه موجود نیست یا حذف شده است.", status=404)
    return _private(FileResponse(p.report.open("rb"), as_attachment=True,
                                 filename=f"report-{p.pk}.png", content_type="image/png"))


@login_required
@never_cache
def reports_zip(request, pk):
    exam = _exam(request.user, pk)
    services.finalize_due(exam.pk)
    if exam.report_files_deleted:
        return HttpResponse("فایل‌های کارنامه حذف شده‌اند.", status=404)
    data = BytesIO()
    with ZipFile(data, "w", ZIP_DEFLATED) as archive:
        for p in exam.participations.filter(submitted_at__isnull=False, result_deleted=False).select_related("student__user"):
            if p.report:
                # UUID avoids duplicate names and unsafe user-supplied archive paths.
                with p.report.open("rb") as file:
                    archive.writestr(f"report-{p.pk}.png", file.read())
    data.seek(0)
    return _private(FileResponse(data, as_attachment=True, filename="exam-reports.zip", content_type="application/zip"))


@login_required
@never_cache
def delete_results(request, pk):
    if not is_school_admin(request.user):
        raise PermissionDenied
    exam = _exam(request.user, pk)
    full = request.GET.get("kind") == "full"
    if request.method == "POST":
        if request.POST.get("confirm") != str(exam.pk):
            return HttpResponse("تأیید حذف معتبر نیست.", status=400)
        try:
            services.purge(pk, request.user, full=full)
            messages.success(request, "نتایج و فایل‌ها حذف شدند." if full else "فایل‌های کارنامه حذف شدند؛ نتایج باقی ماندند.")
        except ValidationError as error:
            _error(request, error)
        return redirect("exam_detail", pk=pk)
    return render(request, "online_exams/delete.html", {"exam": exam, "full": full,
        "file_count": exam.participations.exclude(report="").count(),
        "result_count": exam.participations.filter(started_at__isnull=False, result_deleted=False).count()})


@login_required
@require_POST
def preview(request):
    if not can_manage(request.user):
        raise PermissionDenied
    if len(request.body) > 50000:
        return JsonResponse({"error": "متن طولانی است."}, status=400)
    try:
        data = json.loads(request.body)
        text = data["text"]
        if not isinstance(text, str) or len(text) > 10000:
            raise ValueError
    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
        return JsonResponse({"error": "متن معتبر نیست."}, status=400)
    return JsonResponse({"html": render_text(text)})


@login_required
@require_POST
def reopen(request, pk):
    _exam(request.user, pk)
    try:
        services.reopen(pk, request.user)
    except ValidationError as error:
        _error(request, error)
        return redirect("exam_detail", pk=pk)
    messages.success(request, "آزمون به پیش‌نویس برگشت و تا انتشار دوباره برای دانش‌آموزان نمایش داده نمی‌شود.")
    return redirect("exam_edit", pk=pk)


@login_required
@never_cache
def delete_exam(request, pk):
    exam = _exam(request.user, pk)
    started = exam.participations.filter(started_at__isnull=False).exists()
    if started and not is_school_admin(request.user):
        raise PermissionDenied
    if request.method == "POST":
        if request.POST.get("confirm") != str(exam.pk):
            return HttpResponse("تأیید حذف معتبر نیست.", status=400)
        try:
            services.delete_exam(pk, request.user)
        except ValidationError as error:
            _error(request, error)
            return redirect("exam_detail", pk=pk)
        messages.success(request, "آزمون و پاسخ‌ها و فایل‌های وابسته حذف شدند.")
        return redirect("exam_list")
    return render(request, "online_exams/delete_exam.html", {
        "exam": exam, "started": started, "now": timezone.now(),
        "participant_count": exam.participations.count(),
        "started_count": exam.participations.filter(started_at__isnull=False).count(),
    })

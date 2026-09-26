from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q, Prefetch
from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden
from academic.models import Enrollment
from accounts.choices import Role
from dashboard.xlsx_export import build_routine_report_xlsx

from activitylog.utils import log_activity
from .forms import (
    CafeteriaReceiptUploadForm,
)
from .models import (
    CafeteriaWeek,
    CafeteriaReservation,
    CafeteriaReservationItem,
)

@login_required
@transaction.atomic
def weekly_reservation(request):
    if not hasattr(request.user, "student_profile"):
        return HttpResponseForbidden("این بخش مخصوص دانش‌آموز است.")
    student = request.user.student_profile
    week = get_object_or_404(CafeteriaWeek, is_active=True)
    # Serialize repeated submissions for the same student, including first creation.
    type(student).objects.select_for_update().get(pk=student.pk)
    menus = list(week.menus.all().weekday_order())
    reservation = CafeteriaReservation.objects.filter(student=student, week=week).first()
    locked = reservation and reservation.payment_status in ("paid", "receipt_pending")
    if request.method == "POST" and menus and not locked:
        if reservation is None:
            reservation = CafeteriaReservation.objects.create(student=student, week=week)
        reservation.items.exclude(menu__in=menus).delete()
        for menu in menus:
            CafeteriaReservationItem.objects.update_or_create(
                reservation=reservation, menu=menu, defaults={"wants_food": True})
        reservation.final_amount = sum(menu.price for menu in menus)
        reservation.save(update_fields=["final_amount"])
        return redirect("cafeteria_payment_method", reservation_id=reservation.id)
    return render(request, "cafeteria/weekly_reservation.html", {
        "week": week, "menus": menus, "reservation": reservation,
        "weekly_total": sum(menu.price for menu in menus), "locked": locked,
    })


@login_required
def payment_method(request, reservation_id):

    student = request.user.student_profile

    reservation = get_object_or_404(
        CafeteriaReservation,
        id=reservation_id,
        student=student,
    )

    return render(
        request,
        "cafeteria/payment_method.html",
        {
            "reservation": reservation,
        },
    )


@login_required
def upload_receipt(request, reservation_id):

    student = request.user.student_profile

    reservation = get_object_or_404(
        CafeteriaReservation,
        id=reservation_id,
        student=student,
    )

    if reservation.payment_status in ("paid", "receipt_pending"):
        return redirect("student_dashboard")

    if request.method == "POST":

        form = CafeteriaReceiptUploadForm(
            request.POST,
            request.FILES,
            instance=reservation,
        )

        if form.is_valid():

            reservation = form.save(commit=False)

            reservation.payment_method = "receipt"
            reservation.payment_status = "receipt_pending"

            reservation.save()
            log_activity(
                request,
                action="cafeteria_receipt_uploaded",
                description=(
                    f"فیش غذای {student.user.get_full_name()} "
                    f"به مبلغ {reservation.final_amount} تومان ارسال شد."
                ),
            )

            return redirect("student_dashboard")

    else:

        form = CafeteriaReceiptUploadForm(
            instance=reservation,
        )

    return render(
        request,
        "cafeteria/upload_receipt.html",
        {
            "reservation": reservation,
            "form": form,
        },
    )


@login_required
def pending_receipts(request):

    if not (request.user.is_school_admin or request.user.role == Role.FINANCE):

        if hasattr(request.user, "teacher_profile"):
            return redirect("teacher_dashboard")

        if hasattr(request.user, "student_profile"):
            return redirect("student_dashboard")

        return redirect("user_login")

    query = (request.GET.get("q") or "").strip()
    reservations = (
        CafeteriaReservation.objects.filter(
            receipt_image__isnull=False,
        ).exclude(receipt_image="")
        .prefetch_related(Prefetch("student__enrollments", queryset=Enrollment.objects.filter(is_active=True).select_related("classroom__grade", "academic_year"), to_attr="receipt_enrollments"))
        .select_related(
            "student__user",
            "week",
        )
        .order_by("-created_at")
    )
    if query:
        reservations = reservations.filter(
            Q(student__user__first_name__icontains=query)
            | Q(student__user__last_name__icontains=query)
        )

    week_id = request.GET.get("week", "")
    valid_weeks = {str(pk) for pk in CafeteriaWeek.objects.values_list("pk", flat=True)}
    if week_id in valid_weeks:
        reservations = reservations.filter(week_id=week_id)
    else:
        week_id = ""
    for reservation in reservations:
        enrollments = reservation.student.receipt_enrollments
        matching = [e for e in enrollments if reservation.week and
            e.academic_year.start_date and e.academic_year.end_date and
            e.academic_year.start_date <= reservation.week.start_date <= e.academic_year.end_date]
        if not matching:
            matching = [e for e in enrollments if e.academic_year.status == "active"]
        reservation.student_class = "، ".join(str(e.classroom) for e in matching) or "—"
    if request.GET.get("export") == "xlsx":
        rows = [[r.student.user.first_name, r.student.user.last_name, r.student_class,
                 r.week.title if r.week else "", r.get_payment_status_display()] for r in reservations]
        response = HttpResponse(build_routine_report_xlsx(
            ["نام", "نام خانوادگی", "کلاس", "هفته", "وضعیت"], rows,
            sheet_name="فیش‌های غذا"),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = 'attachment; filename="cafeteria-receipts.xlsx"'
        return response
    return render(
        request,
        "cafeteria/pending_receipts.html",
        {
            "reservations": reservations,
            "query": query, "weeks": CafeteriaWeek.objects.all(), "selected_week": week_id,
        },
    )


@login_required
def review_receipt(request, reservation_id, action):

    if not (request.user.is_school_admin or request.user.role == Role.FINANCE):

        if hasattr(request.user, "teacher_profile"):
            return redirect("teacher_dashboard")

        if hasattr(request.user, "student_profile"):
            return redirect("student_dashboard")

        return redirect("user_login")

    reservation = get_object_or_404(
        CafeteriaReservation,
        id=reservation_id,
        payment_status="receipt_pending",
    )

    if request.method == "POST":

        student_name = reservation.student.user.get_full_name()
        amount = reservation.final_amount

        if action == "approve":

            reservation.payment_status = "paid"

            log_action = "cafeteria_receipt_approved"

            log_description = (
                f"فیش غذای {student_name} "
                f"به مبلغ {amount} تومان تأیید شد."
            )

        elif action == "reject":

            reservation.payment_status = "rejected"

            log_action = "cafeteria_receipt_rejected"

            log_description = (
                f"فیش غذای {student_name} "
                f"به مبلغ {amount} تومان رد شد."
            )

        else:
            return redirect(
                "cafeteria_pending_receipts"
            )

        reservation.save(
            update_fields=["payment_status"]
        )

        log_activity(
            request,
            action=log_action,
            description=log_description,
        )

    return redirect(
        "cafeteria_pending_receipts"
    )

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import (
    CafeteriaWeeklyReservationForm,
    CafeteriaReceiptUploadForm,
)
from .models import (
    CafeteriaWeek,
    CafeteriaReservation,
    CafeteriaReservationItem,
)

@login_required
def weekly_reservation(request):

    student = request.user.student_profile

    week = get_object_or_404(
        CafeteriaWeek,
        is_active=True,
    )

    menus = week.menus.all().order_by("day")

    reservation = CafeteriaReservation.objects.filter(
        student=student,
        week=week,
    ).first()


    if reservation and reservation.payment_status == "paid":
        return redirect("student_dashboard")

    if request.method == "POST":

        form = CafeteriaWeeklyReservationForm(
            request.POST,
            menus=menus,
        )

        if form.is_valid():

            if reservation is None:
                reservation = CafeteriaReservation.objects.create(
                    student=student,
                    week=week,
                )

            for menu in menus:

                field_name = f"menu_{menu.id}"

                wants_food = form.cleaned_data.get(
                    field_name,
                    False,
                )

                CafeteriaReservationItem.objects.update_or_create(
                    reservation=reservation,
                    menu=menu,
                    defaults={
                        "wants_food": wants_food,
                    },
                )

            reservation.final_amount = reservation.total_price
            reservation.save(update_fields=["final_amount"])

            return redirect(
                "cafeteria_payment_method",
                reservation_id=reservation.id,
            )

    else:

        initial = {}

        existing_items = {}

        if reservation is not None:
            existing_items = {
                item.menu_id: item.wants_food
                for item in reservation.items.all()
            }

        for menu in menus:
            initial[f"menu_{menu.id}"] = existing_items.get(
                menu.id,
                False,
            )

        form = CafeteriaWeeklyReservationForm(
            menus=menus,
            initial=initial,
        )

    return render(
        request,
        "cafeteria/weekly_reservation.html",
        {
            "week": week,
            "menus": menus,
            "form": form,
            "reservation": reservation,
        },
    )



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

    if not request.user.is_staff:
        return redirect("student_dashboard")

    reservations = (
        CafeteriaReservation.objects.filter(
            payment_status="receipt_pending",
        )
        .select_related(
            "student__user",
            "week",
        )
        .order_by("-created_at")
    )

    return render(
        request,
        "cafeteria/pending_receipts.html",
        {
            "reservations": reservations,
        },
    )


@login_required
def review_receipt(request, reservation_id, action):

    if not request.user.is_staff:
        return redirect("student_dashboard")

    reservation = get_object_or_404(
        CafeteriaReservation,
        id=reservation_id,
        payment_status="receipt_pending",
    )

    if request.method == "POST":

        if action == "approve":
            reservation.payment_status = "paid"

        elif action == "reject":
            reservation.payment_status = "rejected"

        else:
            return redirect("cafeteria_pending_receipts")

        reservation.save(
            update_fields=["payment_status"]
        )

    return redirect(
        "cafeteria_pending_receipts"
    )
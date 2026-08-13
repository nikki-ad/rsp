from django.urls import path

from . import views


urlpatterns = [
    path(
        "weekly-reservation/",
        views.weekly_reservation,
        name="weekly_reservation",
    ),


    path(
        "reservation/<uuid:reservation_id>/payment/",
        views.payment_method,
        name="cafeteria_payment_method",
    ),


    path(
        "reservation/<uuid:reservation_id>/receipt/",
        views.upload_receipt,
        name="cafeteria_upload_receipt",
    ),


    path(
        "pending-receipts/",
        views.pending_receipts,
        name="cafeteria_pending_receipts",
    ),


    path(
        "reservation/<uuid:reservation_id>/review/<str:action>/",
        views.review_receipt,
        name="cafeteria_review_receipt",
    ),



]
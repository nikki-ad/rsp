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



]
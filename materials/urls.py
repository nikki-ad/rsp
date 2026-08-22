from django.urls import path

from . import views


urlpatterns = [
    path(
        "create/",
        views.create_material,
        name="create_material",
    ),

    path(
        "<uuid:material_id>/download/",
        views.download_material,
        name="download_material",
    ),
]
from django.urls import path
from . import homework_views as views

urlpatterns = [
    path("deficiencies/teacher/", views.deficiency_classrooms, name="teacher_deficiency_classrooms"),
    path("deficiencies/teacher/<uuid:classroom_id>/", views.deficiency_create, name="teacher_deficiency_create"),
    path("deficiencies/calendar/", views.deficiency_calendar, name="deficiency_calendar"),
    path("deficiencies/student/", views.student_deficiency_list, name="student_deficiency_list"),
]

from . import homework_report_views as report_views

urlpatterns += [
    path("deficiencies/report/", report_views.deficiency_report_filter, name="deficiency_report_filter"),
    path("deficiencies/report/download/", report_views.deficiency_report_download, name="deficiency_report_download"),
    path("deficiencies/report/calendar/", report_views.deficiency_report_calendar, name="deficiency_report_calendar"),
]

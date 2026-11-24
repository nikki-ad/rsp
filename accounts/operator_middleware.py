from django.http import HttpResponseForbidden

from .permissions import is_operator


class OperatorAccessMiddleware:
    """Reject other roles' endpoints even if a former role left a profile behind."""

    views = {
        "admin_dashboard", "announcement_create", "classroom_list",
        "manager_material_classrooms", "manager_assignment_classrooms",
        "manager_class_materials", "manager_class_assignments",
        "download_material", "download_assignment_file", "download_assignment_attachment",
        "manage_language_groups", "language_group_material_list",
        "language_group_assignment_list", "download_language_material",
        "download_language_assignment", "online_class_list", "language_online_list",
        "join_online_class", "live_attendance", "exam_list", "exam_detail",
        "exam_report", "exam_reports_zip", "operator_report_cards", "download_report_card", "protected_media",
        "profile", "logout", "user_login", "notification_list", "open_notification",
        "delete_all_notifications", "pwa_manifest", "pwa_service_worker",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view, args, kwargs):
        if not is_operator(request.user):
            return None
        match = request.resolver_match
        if match.namespace or match.url_name not in self.views:
            return HttpResponseForbidden()
        return None

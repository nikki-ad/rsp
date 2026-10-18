"""Install narrow hooks without replacing other deployed web/PWA features."""
from pathlib import Path
import sys


def integrate(root, source, check=False):
    changes = {}

    def patch(filename, old, new, marker):
        path = root / filename
        value = changes.get(path, path.read_text())
        if marker in value:
            return
        if value.count(old) != 1:
            raise SystemExit(f"Expected one integration anchor in {filename}; no files changed.")
        changes[path] = value.replace(old, new, 1)

    urls = root / "assignments/homework_urls.py"
    text = urls.read_text()
    block = (source / "assignments/homework_urls.py").read_text().split("\nfrom . import homework_report_views as report_views", 1)[1]
    if "from . import homework_report_views as report_views" not in text:
        changes[urls] = text.rstrip() + "\n\nfrom . import homework_report_views as report_views" + block

    patch("dashboard/views.py", "def admin_dashboard(request):\n",
          'def admin_dashboard(request):\n    if request.user.role == Role.OPERATOR and not is_school_admin(request.user):\n        return render(request, "dashboard/operator_dashboard.html")\n',
          'return render(request, "dashboard/operator_dashboard.html")')
    patch("accounts/permissions.py", "def post_login_redirect_name(user):\n    if is_school_admin(user):",
          "def post_login_redirect_name(user):\n    if is_school_admin(user) or user.role == Role.OPERATOR:",
          "if is_school_admin(user) or user.role == Role.OPERATOR:")
    patch("dashboard/templates/dashboard/admin_dashboard.html", '{% extends "base.html" %}',
          '{% extends "base.html" %}\n{% load homework_reports %}', "{% load homework_reports %}")
    patch("dashboard/templates/dashboard/admin_dashboard.html", "{% if active_year %}",
          "{% homework_report_dialog %}\n\n{% if active_year %}", "{% homework_report_dialog %}")
    patch("templates/components/sidebar.html", '            {% elif user.role == "finance" %}',
          '            {% elif user.role == "operator" %}\n                <a href="{% url \'admin_dashboard\' %}" class="{% if url_name == \'admin_dashboard\' %}active{% endif %}">داشبورد مدیریت</a>\n                <a href="{% url \'deficiency_report_filter\' %}">گزارش نقص تکلیف‌ها</a>\n\n            {% elif user.role == "finance" %}',
          '{% elif user.role == "operator" %}')
    if not check:
        for path, text in changes.items():
            path.write_text(text)


if __name__ == "__main__":
    integrate(Path(sys.argv[1]), Path(sys.argv[2]), check="--check" in sys.argv[3:])

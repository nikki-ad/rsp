"""Add integration hooks while retaining unrelated live web/PWA changes."""
import sys
from pathlib import Path


def integrate(root, check=False):
    changes = {}
    for filename, hook in [
        ("assignments/models.py", "from .homework_models import HomeworkDeficiency  # noqa: E402,F401"),
        ("assignments/urls.py", "from .homework_urls import urlpatterns as homework_patterns\nurlpatterns += homework_patterns"),
    ]:
        path = root / filename
        text = path.read_text()
        marker = hook.splitlines()[0]
        if marker not in text:
            changes[path] = text.rstrip() + "\n\n\n" + hook + "\n"
        elif hook not in text:
            raise SystemExit(f"Unexpected existing integration in {filename}; no files changed.")

    path = root / "templates/components/sidebar.html"
    text = path.read_text()
    for anchor_name, route, label, active in [
        ("teacher_assignment_list", "teacher_deficiency_classrooms", "ثبت نقص تکلیف",
         "url_name == 'teacher_deficiency_classrooms' or url_name == 'teacher_deficiency_create'"),
        ("student_assignment_list", "student_deficiency_list", "مشاهده نقص تکلیف",
         "url_name == 'student_deficiency_list'"),
    ]:
        marker = "{% url '" + route + "' %}"
        if marker in text:
            continue
        anchor = '                <a href="{% url \'' + anchor_name + '\' %}"'
        if text.count(anchor) != 1:
            raise SystemExit(f"Expected one sidebar anchor for {anchor_name}; no files changed.")
        link = '                <a href="' + marker + '" class="{% if ' + active + ' %}active{% endif %}">' + label + '</a>\n'
        text = text.replace(anchor, link + anchor)
    changes[path] = text
    if not check:
        for path, value in changes.items():
            path.write_text(value)


if __name__ == "__main__":
    integrate(Path(sys.argv[1]), check="--check" in sys.argv[2:])

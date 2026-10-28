"""Template-only server fix. Run: sudo python3 fix-student-report-sidebar.py"""
from pathlib import Path
from datetime import datetime
import shutil

app = Path("/srv/rsp")
sidebar = app / "templates/components/sidebar.html"
dashboard = app / "accounts/templates/accounts/student_dashboard.html"
link = """                <a href="{% url 'student_dashboard' %}#report-cards">کارنامه‌ها</a>
"""
changes = {}
s = sidebar.read_text()
if link.strip() not in s:
    marker = """                <a href="{% url 'student_material_list' %}" """
    if s.count(marker) != 1:
        raise SystemExit("Unexpected sidebar; no files changed")
    s = s.replace(marker, link + marker, 1)
changes[sidebar] = s
s = dashboard.read_text()
if 'id="report-cards"' not in s:
    marker = '<div class="dashboard-section"><h2>📄 کارنامه‌های من</h2>'
    if s.count(marker) != 1:
        raise SystemExit("Unexpected dashboard; no files changed")
    s = s.replace(marker, '<div class="dashboard-section" id="report-cards" style="scroll-margin-top: 90px;"><h2>📄 کارنامه‌های من</h2>', 1)
changes[dashboard] = s
backup = Path("/srv/rsp-backups") / ("report-sidebar-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
backup.mkdir(parents=True, mode=0o700)
try:
    for path in changes:
        target = backup / path.relative_to(app)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    for path, content in changes.items():
        path.write_text(content)
except Exception:
    for path in changes:
        saved = backup / path.relative_to(app)
        if saved.exists():
            shutil.copy2(saved, path)
    raise
print("Sidebar fixed. No database or uploaded files changed.")
print("Template backup:", backup)

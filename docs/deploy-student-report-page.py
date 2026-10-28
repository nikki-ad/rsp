#!/usr/bin/env python3
"""Deploy student report page without migrations or database writes."""
import os
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

app = Path("/srv/rsp")
source = Path(__file__).resolve().parent.parent
expected = {'accounts/views.py': '270b7dce1a32f60534bb2359212a8c9d99f73ff98143956ecd79f1949244db5e', 'accounts/templates/accounts/student_dashboard.html': '1c70bb6d1cf97e3ee6d9058a8a5157a053d94540c4b2a307a142f730537ef377', 'reports/views.py': '5bc6950af7ab0fe1e598a7ca384fc1c6ab666fb30b623be2f3fac5579d51dd21', 'reports/urls.py': '8b2fb35a1924aa3308cf7e7f46596a9a862aa319d4167417b1b6e74768f74c9e', 'templates/components/sidebar.html': '2e06fbdaee019b4c19fbe30274f4ace3c4a70f46b38c0dceb168691110b6521b'}
new_file = "reports/templates/reports/student_report_cards.html"
def normalize(text):
    return text.replace(' style="scroll-margin-top: 90px;"', '')
if os.geteuid() != 0:
    raise SystemExit("Run with sudo")
changes = {}
for name, old in expected.items():
    current = (app / name).read_text()
    updated = (source / name).read_text()
    if hashlib.sha256(normalize(current).encode()).hexdigest() != old and normalize(current) != normalize(updated):
        raise SystemExit("Unexpected installed file; no files changed: " + name)
    changes[name] = updated
target = app / new_file
if target.exists() and target.read_text() != (source / new_file).read_text():
    raise SystemExit("Unexpected report template; no files changed")
changes[new_file] = (source / new_file).read_text()
Path("/srv/rsp-backups").mkdir(exist_ok=True)
backup = Path(tempfile.mkdtemp(prefix="report-page-", dir="/srv/rsp-backups"))
existed = []
for name in changes:
    path = app / name
    if path.exists():
        saved = backup / name
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, saved)
        existed.append(name)
try:
    subprocess.run(["systemctl", "stop", "rsp"], check=True)
    for name, content in changes.items():
        path = app / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        if name not in existed:
            path.chmod(0o644)
            owner = (app / "manage.py").stat()
            os.chown(path, owner.st_uid, owner.st_gid)
    subprocess.run(["bash", "-c", 'set -a; source /etc/rsp/rsp.env; set +a; cd /srv/rsp; exec venv/bin/python manage.py check'], check=True)
    subprocess.run(["systemctl", "start", "rsp"], check=True)
    subprocess.run(["systemctl", "is-active", "--quiet", "rsp"], check=True)
except BaseException:
    for name in changes:
        if name in existed:
            shutil.copy2(backup / name, app / name)
        else:
            (app / name).unlink(missing_ok=True)
    subprocess.run(["systemctl", "restart", "rsp"], check=False)
    raise
print("Student report page deployed. Database and uploaded files unchanged.")
print("Backup:", backup)

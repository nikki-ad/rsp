#!/usr/bin/env bash
# Run as root: bash docs/deploy-teacher-feedback.sh SOURCE_DIR NEW_REVISION
set -Eeuo pipefail

app=/srv/rsp
source_dir=$(realpath "${1:?source directory required}")
new=${2:?new revision required}
old=$(cat "$app/.deployment-revision")
py=$app/venv/bin/python
test "$EUID" -eq 0
mkdir -p /srv/rsp-backups
[[ "$new" =~ ^[0-9a-f]{40}$ ]]
[[ "$old" =~ ^[0-9a-f]{40}$ ]]
command -v pg_dump >/dev/null
test -x "$py"
systemctl is-active --quiet rsp

files=(
  accounts/templates/accounts/student_dashboard.html
  assignments/forms.py
  assignments/models.py
  assignments/templates/assignments/evaluate_submission.html
  assignments/templates/assignments/student_assignment_list.html
  assignments/templates/assignments/submissions.html
  assignments/urls.py
  assignments/views.py
  language_unit/forms.py
  language_unit/models.py
  language_unit/templates/language_unit/student_dashboard.html
  language_unit/templates/language_unit/submissions.html
  language_unit/urls.py
  language_unit/views.py
  assignments/migrations/0006_assignmentsubmission_feedback_file_and_more.py
  core/feedback_access.py
  core/feedback_forms.py
  language_unit/migrations/0004_languageassignmentsubmission_feedback_file_and_more.py
  static/js/teacher-feedback.js
  templates/components/teacher_feedback.html
)

for file in "${files[@]}"; do test -f "$source_dir/$file"; done

# Refuse to overwrite unreviewed server edits; web and PWA share these baseline files.
test "$(sha256sum "$app/accounts/templates/accounts/student_dashboard.html" | cut -d " " -f1)" = "58e4773f202dc8910c2ceb31df107e3c844d4e03b5097af0ec0095b74902b1e8"
test "$(sha256sum "$app/assignments/forms.py" | cut -d " " -f1)" = "b51fab2bcfe94f5975c0817ff6bdaf6e35fc00f3acbc984ed593eb3bb3f860c3"
test "$(sha256sum "$app/assignments/models.py" | cut -d " " -f1)" = "27a5da28c720387cd1cd05eaed8ccf72f6d3227652483f1cb329bcc314183004"
test "$(sha256sum "$app/assignments/templates/assignments/evaluate_submission.html" | cut -d " " -f1)" = "3463a0b835e837e67f0093a3b4732e4faec111c64f21fb3b61245822c3e8ac90"
test "$(sha256sum "$app/assignments/templates/assignments/student_assignment_list.html" | cut -d " " -f1)" = "dfacea0d815070d73786d4079210eb817f0e0499d3bf157d2c62c19beff8a724"
test "$(sha256sum "$app/assignments/templates/assignments/submissions.html" | cut -d " " -f1)" = "ea3f90a5766968c0f544313ae1fc125984e91e53df210162b33bdbe01af30a91"
test "$(sha256sum "$app/assignments/urls.py" | cut -d " " -f1)" = "9192655ed0d18dbfbcf2c4b9f77e70f32b25c917aa08ee72ae4291439ef47139"
test "$(sha256sum "$app/assignments/views.py" | cut -d " " -f1)" = "9d2169274c9d7cace697626e244822fcaae28def39bad1c968433159dd527a28"
test "$(sha256sum "$app/language_unit/forms.py" | cut -d " " -f1)" = "6391af99f065c029238aa0633b92fa3ddbc79b6f944669ae5761e86d35aedb74"
test "$(sha256sum "$app/language_unit/models.py" | cut -d " " -f1)" = "b439a89e7503bd4cb781e84ca6f9a2ebea2eae3b95642c857969681ab5211065"
test "$(sha256sum "$app/language_unit/templates/language_unit/student_dashboard.html" | cut -d " " -f1)" = "bf1eb468f7508918d138a80d273b63d72d106494cb1dd73a5421db24d70c80c5"
test "$(sha256sum "$app/language_unit/templates/language_unit/submissions.html" | cut -d " " -f1)" = "bf90674189e2d48b457c6ed30625fed742b202551e2f1a97886c534e9d562d51"
test "$(sha256sum "$app/language_unit/urls.py" | cut -d " " -f1)" = "0afd76694221582373a9aeae3f649e66d90cd304d01daec053680c0bd4f50246"
test "$(sha256sum "$app/language_unit/views.py" | cut -d " " -f1)" = "9b4bba8eaeb2d2f2ebd2babaf841ea7fe0b1834a75d660aa2877c567c5a8f258"

backup=$(mktemp -d /srv/rsp-backups/teacher-feedback-XXXXXXXX)
chmod 700 "$backup"
cp -a "$app/.deployment-revision" "$backup/revision"
touch "$backup/existing.txt" "$backup/new.txt"
for file in "${files[@]}"; do
  if [ -f "$app/$file" ]; then
    mkdir -p "$backup/files/$(dirname "$file")"
    cp -a "$app/$file" "$backup/files/$file"
    printf '%s\n' "$file" >> "$backup/existing.txt"
  else
    printf '%s\n' "$file" >> "$backup/new.txt"
  fi
done

django() (
  set -a
  source /etc/rsp/rsp.env
  set +a
  cd "$app"
  "$py" manage.py "$@"
)

rollback() {
  code=$?
  trap - ERR
  set +e
  systemctl stop rsp
  while IFS= read -r file; do cp -a "$backup/files/$file" "$app/$file"; done < "$backup/existing.txt"
  while IFS= read -r file; do rm -f "$app/$file"; done < "$backup/new.txt"
  cp -a "$backup/revision" "$app/.deployment-revision"
  # Additive migration columns are intentionally retained; old code ignores them.
  django collectstatic --noinput
  systemctl start rsp
  printf 'Deployment failed; previous files restored. Backup: %s\n' "$backup" >&2
  exit "$code"
}
trap rollback ERR

systemctl stop rsp
export RSP_FEEDBACK_BACKUP_PATH="$backup/database.dump"
django shell -c '
import os, subprocess
from django.conf import settings
config = settings.DATABASES["default"]
assert "postgresql" in config["ENGINE"], "PostgreSQL expected"
env = os.environ.copy()
env["PGPASSWORD"] = str(config.get("PASSWORD") or "")
command = ["pg_dump", "--format=custom", "--file", os.environ["RSP_FEEDBACK_BACKUP_PATH"]]
for key, option in [("HOST", "--host"), ("PORT", "--port"), ("USER", "--username")]:
    if config.get(key): command += [option, str(config[key])]
command += [str(config["NAME"])]
subprocess.run(command, env=env, check=True)
'
test -s "$backup/database.dump"
for file in "${files[@]}"; do
  mkdir -p "$app/$(dirname "$file")"
  if [ -f "$app/$file" ]; then
    cp "$source_dir/$file" "$app/$file"
  else
    install -m 644 "$source_dir/$file" "$app/$file"
    chown --reference="$app/manage.py" "$app/$file"
  fi
done
django migrate assignments --noinput
django migrate language_unit --noinput
django check --deploy
django collectstatic --noinput
systemctl start rsp
systemctl is-active --quiet rsp

# Wait briefly for Gunicorn to accept requests after systemd reports active.
healthy=false
for attempt in {1..10}; do
  status=$(curl --connect-timeout 3 --max-time 5 -ksS -o /dev/null -w '%{http_code}' \
    --resolve rsp.roshangaran-elementary.com:443:127.0.0.1 \
    https://rsp.roshangaran-elementary.com/dashboard/ || true)
  if [[ "$status" == 302 || "$status" == 200 ]]; then healthy=true; break; fi
  sleep 1
done
test "$healthy" = true
printf '%s\n' "$new" > "$app/.deployment-revision"
trap - ERR
printf 'Teacher feedback deployed: %s\nBackup: %s\nHTTP %s\n' "$new" "$backup" "$status"

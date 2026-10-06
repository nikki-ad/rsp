#!/usr/bin/env bash
# bash docs/deploy-language-teachers.sh SOURCE_DIR NEW_REVISION
set -Eeuo pipefail
app=/srv/rsp
source_dir=$(realpath "${1:?source directory required}")
new=${2:?new revision required}
old=1808fcc9b9fac0cc09692454e188026875cd1b37
py=$app/venv/bin/python
test "$EUID" -eq 0
[[ "$new" =~ ^[0-9a-f]{40}$ ]]
test "$(cat "$app/.deployment-revision")" = "$old"
test -x "$py"
command -v pg_dump >/dev/null
systemctl is-active --quiet rsp
files=(
  accounts/admin.py
  accounts/forms.py
  accounts/migrations/0008_teacherprofile_is_language_teacher.py
  accounts/models.py
  accounts/permissions.py
  accounts/views.py
  assignments/views.py
  dashboard/crud.py
  dashboard/forms.py
  dashboard/templates/dashboard/form.html
  dashboard/templates/dashboard/teacher_list.html
  language_unit/content_views.py
  language_unit/templates/language_unit/assignment_attachments.html
  language_unit/templates/language_unit/content_list.html
  language_unit/templates/language_unit/group_detail.html
  language_unit/templates/language_unit/manage_groups.html
  language_unit/templates/language_unit/material_attachment.html
  language_unit/templates/language_unit/teacher_dashboard.html
  language_unit/urls.py
  language_unit/views.py
  materials/forms.py
  materials/views.py
  messaging/views.py
  online_classes/views.py
  static/js/teacher-unit.js
  templates/components/sidebar.html
)
for file in "${files[@]}"; do test -f "$source_dir/$file"; done
mkdir -p /srv/rsp-backups
backup=$(mktemp -d /srv/rsp-backups/language-teachers-XXXXXXXX)
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
  # Migration only adds a default-false column; leave it in place on file rollback.
  # This is compatible with the previous code and avoids restoring live user data.
  django collectstatic --noinput
  systemctl start rsp
  printf 'Deployment failed; previous files restored. Backup: %s\n' "$backup" >&2
  exit "$code"
}
trap rollback ERR
systemctl stop rsp
export RSP_LANGUAGE_BACKUP_PATH="$backup/database.dump"
django shell -c '
import os, subprocess
from django.conf import settings
config = settings.DATABASES["default"]
assert "postgresql" in config["ENGINE"], "PostgreSQL expected"
env = os.environ.copy()
env["PGPASSWORD"] = str(config.get("PASSWORD") or "")
command = ["pg_dump", "--format=custom", "--file", os.environ["RSP_LANGUAGE_BACKUP_PATH"]]
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
django migrate --noinput
django check --deploy
django collectstatic --noinput
systemctl start rsp
systemctl is-active --quiet rsp
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
printf 'Language teachers deployed: %s\nBackup: %s\nHTTP %s\n' "$new" "$backup" "$status"

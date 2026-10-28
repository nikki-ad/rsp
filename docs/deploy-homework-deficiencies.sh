#!/usr/bin/env bash
# Run as root: bash docs/deploy-homework-deficiencies.sh SOURCE_DIR NEW_REVISION
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
  assignments/homework_models.py
  assignments/homework_forms.py
  assignments/homework_views.py
  assignments/homework_urls.py
  assignments/migrations/0007_homeworkdeficiency.py
  assignments/templates/assignments/deficiency_classrooms.html
  assignments/templates/assignments/deficiency_form.html
  assignments/templates/assignments/deficiency_list.html
  static/css/homework-deficiency.css
  static/js/homework-deficiency.js
  assignments/models.py
  assignments/urls.py
  templates/components/sidebar.html
)

for file in "${files[@]}"; do test -f "$source_dir/$file"; done
test -f "$source_dir/docs/integrate-homework-deficiencies.py"

# Validate the existing integration anchors before stopping the service.
"$py" "$source_dir/docs/integrate-homework-deficiencies.py" "$app" --check

backup=$(mktemp -d /srv/rsp-backups/homework-deficiencies-XXXXXXXX)
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

# This additive migration follows the previously installed teacher feedback release.
django shell -c '
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
assert ("assignments", "0006_assignmentsubmission_feedback_file_and_more") in MigrationRecorder(connection).applied_migrations(), "Install teacher feedback first; no server files were changed."
'

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
export RSP_DEFICIENCY_BACKUP_PATH="$backup/database.dump"
django shell -c '
import os, subprocess
from django.conf import settings
config = settings.DATABASES["default"]
assert "postgresql" in config["ENGINE"], "PostgreSQL expected"
env = os.environ.copy()
env["PGPASSWORD"] = str(config.get("PASSWORD") or "")
command = ["pg_dump", "--format=custom", "--file", os.environ["RSP_DEFICIENCY_BACKUP_PATH"]]
for key, option in [("HOST", "--host"), ("PORT", "--port"), ("USER", "--username")]:
    if config.get(key): command += [option, str(config[key])]
command += [str(config["NAME"])]
subprocess.run(command, env=env, check=True)
'
test -s "$backup/database.dump"
for file in "${files[@]}"; do
  case "$file" in assignments/models.py|assignments/urls.py|templates/components/sidebar.html) continue ;; esac
  mkdir -p "$app/$(dirname "$file")"
  if [ -f "$app/$file" ]; then
    cp "$source_dir/$file" "$app/$file"
  else
    install -m 644 "$source_dir/$file" "$app/$file"
    chown --reference="$app/manage.py" "$app/$file"
  fi
done
"$py" "$source_dir/docs/integrate-homework-deficiencies.py" "$app"
django migrate assignments --noinput
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
printf 'Homework deficiencies deployed: %s\nBackup: %s\nHTTP %s\n' "$new" "$backup" "$status"

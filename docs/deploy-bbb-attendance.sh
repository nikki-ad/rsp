#!/usr/bin/env bash
# Run as root: bash docs/deploy-bbb-attendance.sh SOURCE_DIR NEW_REVISION
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
  online_classes/models.py
  online_classes/services.py
  online_classes/views.py
  online_classes/urls.py
  online_classes/templates/online_classes/live_attendance.html
  dashboard/templates/dashboard/online_class_manage_list.html
  online_classes/attendance.py
  online_classes/migrations/0002_bbbattendancehook_bbbattendanceevent.py
  online_classes/management/commands/register_bbb_attendance.py
  static/js/attendance-snapshot.js
)

for file in "${files[@]}"; do test -f "$source_dir/$file"; done

# Refuse unexpected local edits before stopping the running service.
if [ "$(sha256sum "$app/online_classes/models.py" | cut -d ' ' -f1)" != "5fa5050342962e8b8845227abdf62e499d455651295fa05f64b5a2d6748dd87e" ]; then
  printf 'Unexpected deployed version of online_classes/models.py; nothing changed.\n' >&2
  exit 1
fi
if [ "$(sha256sum "$app/online_classes/services.py" | cut -d ' ' -f1)" != "5dbe203f1e0397f2d1a8236bf7fb5b4e20dcb68c3d9c403ac835fe2a4c9b1ace" ]; then
  printf 'Unexpected deployed version of online_classes/services.py; nothing changed.\n' >&2
  exit 1
fi
if [ "$(sha256sum "$app/online_classes/views.py" | cut -d ' ' -f1)" != "58fc45dc66bfc30602e006102bb7f3d38e8f377264608b610e1ac1d795910e75" ]; then
  printf 'Unexpected deployed version of online_classes/views.py; nothing changed.\n' >&2
  exit 1
fi
if [ "$(sha256sum "$app/online_classes/urls.py" | cut -d ' ' -f1)" != "27a68f0e36f5aefb95273b7e7fbe7c48817283dcb2e64b60376dc91f9ee1d3e6" ]; then
  printf 'Unexpected deployed version of online_classes/urls.py; nothing changed.\n' >&2
  exit 1
fi
if [ "$(sha256sum "$app/online_classes/templates/online_classes/live_attendance.html" | cut -d ' ' -f1)" != "78e99e05e749a8874015370e638d4091671fefa4f95b0b4cfaef39f26041bc7b" ]; then
  printf 'Unexpected deployed version of online_classes/templates/online_classes/live_attendance.html; nothing changed.\n' >&2
  exit 1
fi
if [ "$(sha256sum "$app/dashboard/templates/dashboard/online_class_manage_list.html" | cut -d ' ' -f1)" != "52af01d131f4ca5ed3d62175ea5417c2f9fe130c15d4b4d8478d490b2dcba219" ]; then
  printf 'Unexpected deployed version of dashboard/templates/dashboard/online_class_manage_list.html; nothing changed.\n' >&2
  exit 1
fi

backup=$(mktemp -d /srv/rsp-backups/bbb-attendance-XXXXXXXX)
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
  # Additive attendance tables are retained on rollback; old code ignores them.
  django collectstatic --noinput
  systemctl start rsp
  printf 'Deployment failed; previous files restored. Backup: %s\n' "$backup" >&2
  exit "$code"
}
trap rollback ERR

systemctl stop rsp
export RSP_ATTENDANCE_BACKUP_PATH="$backup/database.dump"
django shell -c '
import os, subprocess
from django.conf import settings
config = settings.DATABASES["default"]
assert "postgresql" in config["ENGINE"], "PostgreSQL expected"
env = os.environ.copy()
env["PGPASSWORD"] = str(config.get("PASSWORD") or "")
command = ["pg_dump", "--format=custom", "--file", os.environ["RSP_ATTENDANCE_BACKUP_PATH"]]
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
django migrate online_classes --noinput
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
printf 'BBB attendance deployed: %s\nBackup: %s\nHTTP %s\n' "$new" "$backup" "$status"

# Registration support and actual event delivery are separate from application health.
if ! django register_bbb_attendance; then
  printf 'Attendance hook registration requires checking in the manager panel.\n' >&2
fi

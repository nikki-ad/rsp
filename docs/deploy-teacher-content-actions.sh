#!/usr/bin/env bash
# Run as root: bash docs/deploy-teacher-content-actions.sh SOURCE_DIR NEW_REVISION
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
  accounts/templates/accounts/teacher_class_assignment_list.html
  accounts/templates/accounts/teacher_class_detail.html
  accounts/templates/accounts/teacher_class_material_list.html
  assignments/templates/assignments/teacher_assignment_list.html
  assignments/views.py
  materials/templates/materials/teacher_material_list.html
  materials/views.py
  materials/templates/materials/attachments.html
)

for file in "${files[@]}"; do test -f "$source_dir/$file"; done

# Stop before modifying files if the server differs from the reviewed baseline.
test "$(sha256sum "$app/accounts/templates/accounts/teacher_class_assignment_list.html" | cut -d " " -f1)" = "0bd105085158ade71e18122a45fdb8a233a5095ed9a5e74d0eed79f37e1797d4"
test "$(sha256sum "$app/accounts/templates/accounts/teacher_class_detail.html" | cut -d " " -f1)" = "892043dbacb216718fb81b98e892898c9d5f7cd31178ce8bf316b4a1aabb0d63"
test "$(sha256sum "$app/accounts/templates/accounts/teacher_class_material_list.html" | cut -d " " -f1)" = "9dddc7fa31ed485d43a170656cceb6cbf18632b03992106bb36f9836c8dd148a"
test "$(sha256sum "$app/assignments/templates/assignments/teacher_assignment_list.html" | cut -d " " -f1)" = "01852ad866c45fb7cd98abb70153c9c408f2a24400cb51815ad7a76813612a05"
test "$(sha256sum "$app/assignments/views.py" | cut -d " " -f1)" = "e6b3c2580b8316719dabd5810ecb89c1a065018ea71ac0f8b802372e26cf7957"
test "$(sha256sum "$app/materials/templates/materials/teacher_material_list.html" | cut -d " " -f1)" = "5397da3a57f046f2374bfc64fa78e709cd918d54a3692604f8fb3d358b15b451"
test "$(sha256sum "$app/materials/views.py" | cut -d " " -f1)" = "4bb23083ed88eb5b5d4e77821dd7cc011cb8598c26fdc567a89e1da9ffdb378b"

backup=$(mktemp -d /srv/rsp-backups/teacher-content-actions-XXXXXXXX)
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
  # No database schema changes in this release.
  django collectstatic --noinput
  systemctl start rsp
  printf 'Deployment failed; previous files restored. Backup: %s\n' "$backup" >&2
  exit "$code"
}
trap rollback ERR

systemctl stop rsp
export RSP_CONTENT_BACKUP_PATH="$backup/database.dump"
django shell -c '
import os, subprocess
from django.conf import settings
config = settings.DATABASES["default"]
assert "postgresql" in config["ENGINE"], "PostgreSQL expected"
env = os.environ.copy()
env["PGPASSWORD"] = str(config.get("PASSWORD") or "")
command = ["pg_dump", "--format=custom", "--file", os.environ["RSP_CONTENT_BACKUP_PATH"]]
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
printf 'Teacher content actions deployed: %s\nBackup: %s\nHTTP %s\n' "$new" "$backup" "$status"

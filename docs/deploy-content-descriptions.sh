#!/usr/bin/env bash
# Run as root: bash docs/deploy-content-descriptions.sh SOURCE_DIR NEW_REVISION
set -Eeuo pipefail

app=/srv/rsp
source_dir=$(realpath "${1:?source directory required}")
new=${2:?new revision required}
old=fecf41b6b86dd9377a71995ded587f496f2b0ed8
py=$app/venv/bin/python
test "$EUID" -eq 0
mkdir -p /srv/rsp-backups
[[ "$new" =~ ^[0-9a-f]{40}$ ]]
test "$(cat "$app/.deployment-revision")" = "$old"
test -x "$py"
systemctl is-active --quiet rsp

files=(
  accounts/templates/accounts/student_dashboard.html
  accounts/templates/accounts/teacher_class_assignment_list.html
  accounts/templates/accounts/teacher_class_detail.html
  accounts/templates/accounts/teacher_class_material_list.html
  assignments/forms.py
  assignments/templates/assignments/student_assignment_list.html
  assignments/templates/assignments/submit_assignment.html
  assignments/templates/assignments/teacher_assignment_list.html
  core/uploads.py
  dashboard/templates/dashboard/classroom_content.html
  language_unit/forms.py
  language_unit/templates/language_unit/group_detail.html
  language_unit/templates/language_unit/student_dashboard.html
  materials/forms.py
  materials/templates/materials/student_material_list.html
  materials/templates/materials/teacher_material_list.html
)
for file in "${files[@]}"; do test -f "$source_dir/$file"; done

backup=$(mktemp -d /srv/rsp-backups/content-descriptions-XXXXXXXX)
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
  django collectstatic --noinput
  systemctl start rsp
  printf 'Deployment failed; previous files restored. Backup: %s\n' "$backup" >&2
  exit "$code"
}
trap rollback ERR

systemctl stop rsp
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
printf 'Content descriptions deployed: %s\nBackup: %s\nHTTP %s\n' "$new" "$backup" "$status"

#!/usr/bin/env bash
# Run as root: bash docs/deploy-language-online-classes.sh SOURCE_DIR NEW_REVISION
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
  dashboard/crud.py
  dashboard/forms.py
  dashboard/templates/dashboard/online_class_manage_list.html
  language_unit/templates/language_unit/manage_groups.html
  language_unit/templates/language_unit/student_dashboard.html
  language_unit/templates/language_unit/teacher_dashboard.html
  language_unit/urls.py
  online_classes/migrations/0002_onlineclass_is_language.py
  online_classes/models.py
  online_classes/templates/online_classes/online_class_list.html
  online_classes/views.py
  static/js/online-class-students.js
)

for file in "${files[@]}"; do test -f "$source_dir/$file"; done

test "$(sha256sum "$app/dashboard/crud.py" | cut -d " " -f1)" = "9d1ceb95728d4c83476d0f78404f8e6a4ec792358e6fb32e64b209c7db6f2c54" || cmp -s "$app/dashboard/crud.py" "$source_dir/dashboard/crud.py"
test "$(sha256sum "$app/dashboard/forms.py" | cut -d " " -f1)" = "3465b723f1fb6cfab9a7869a5301e2fcafa844d33a7f6b2036d6d2fc3abb651a" || cmp -s "$app/dashboard/forms.py" "$source_dir/dashboard/forms.py"
test "$(sha256sum "$app/dashboard/templates/dashboard/online_class_manage_list.html" | cut -d " " -f1)" = "52af01d131f4ca5ed3d62175ea5417c2f9fe130c15d4b4d8478d490b2dcba219" || cmp -s "$app/dashboard/templates/dashboard/online_class_manage_list.html" "$source_dir/dashboard/templates/dashboard/online_class_manage_list.html"
test "$(sha256sum "$app/language_unit/templates/language_unit/manage_groups.html" | cut -d " " -f1)" = "6acfc4bd879326bebbcbddb786ff780f1fca735fd4174fae9f280d5ad88200e6" || cmp -s "$app/language_unit/templates/language_unit/manage_groups.html" "$source_dir/language_unit/templates/language_unit/manage_groups.html"
test "$(sha256sum "$app/language_unit/templates/language_unit/student_dashboard.html" | cut -d " " -f1)" = "e7544dc23af26e7b97f7642df739ef88011118bafc5f39c5fb78fafe4a1ec1e3" || cmp -s "$app/language_unit/templates/language_unit/student_dashboard.html" "$source_dir/language_unit/templates/language_unit/student_dashboard.html"
test "$(sha256sum "$app/language_unit/templates/language_unit/teacher_dashboard.html" | cut -d " " -f1)" = "8a786f3bacf4fed34672a585ebddaa333a249a7cbb966cc55a2067d4ed975ad7" || cmp -s "$app/language_unit/templates/language_unit/teacher_dashboard.html" "$source_dir/language_unit/templates/language_unit/teacher_dashboard.html"
test "$(sha256sum "$app/language_unit/urls.py" | cut -d " " -f1)" = "c14cc26fe0f9a2ef6e9bbb332c99ad15d53fa84d16378e5d3123f119f229c960" || cmp -s "$app/language_unit/urls.py" "$source_dir/language_unit/urls.py"
test ! -e "$app/online_classes/migrations/0002_onlineclass_is_language.py" || cmp -s "$app/online_classes/migrations/0002_onlineclass_is_language.py" "$source_dir/online_classes/migrations/0002_onlineclass_is_language.py"
test "$(sha256sum "$app/online_classes/models.py" | cut -d " " -f1)" = "5fa5050342962e8b8845227abdf62e499d455651295fa05f64b5a2d6748dd87e" || cmp -s "$app/online_classes/models.py" "$source_dir/online_classes/models.py"
test "$(sha256sum "$app/online_classes/templates/online_classes/online_class_list.html" | cut -d " " -f1)" = "ce8eaefa8366f3261496de85ff6f703129f06accaea15c062b246ffd4473406a" || cmp -s "$app/online_classes/templates/online_classes/online_class_list.html" "$source_dir/online_classes/templates/online_classes/online_class_list.html"
test "$(sha256sum "$app/online_classes/views.py" | cut -d " " -f1)" = "58fc45dc66bfc30602e006102bb7f3d38e8f377264608b610e1ac1d795910e75" || cmp -s "$app/online_classes/views.py" "$source_dir/online_classes/views.py"
test "$(sha256sum "$app/static/js/online-class-students.js" | cut -d " " -f1)" = "40b482bc91536b57e4297d4dadc125ef5373381e2617648c1f549ec2e4de1874" || cmp -s "$app/static/js/online-class-students.js" "$source_dir/static/js/online-class-students.js"

backup=$(mktemp -d /srv/rsp-backups/language-online-classes-XXXXXXXX)
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
  # The additive is_language column is intentionally retained on rollback.
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
printf 'Language online classes deployed: %s\nBackup: %s\nHTTP %s\n' "$new" "$backup" "$status"

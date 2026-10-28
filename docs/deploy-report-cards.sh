#!/usr/bin/env bash
# Run as root: bash docs/deploy-report-cards.sh SOURCE_DIR NEW_REVISION
set -Eeuo pipefail
app=/srv/rsp
source_dir=$(realpath "${1:?source directory required}")
new=${2:?new revision required}
old=$(cat "$app/.deployment-revision")
py=$app/venv/bin/python
test "$EUID" -eq 0
[[ "$new" =~ ^[0-9a-f]{40}$ && "$old" =~ ^[0-9a-f]{40}$ ]]
test -x "$py"
command -v pg_dump >/dev/null
systemctl is-active --quiet rsp
files=(
  accounts/templates/accounts/student_dashboard.html
  accounts/views.py
  dashboard/crud.py
  dashboard/forms.py
  dashboard/templates/dashboard/form.html
  dashboard/templates/dashboard/report_card_list.html
  dashboard/templates/dashboard/report_card_classes.html
  dashboard/templates/dashboard/report_card_students.html
  dashboard/urls.py
  reports/admin.py
  reports/models.py
  reports/views.py
  reports/migrations/0002_alter_studentreportcard_file_and_more.py
  static/js/report-student-search.js
)
for file in "${files[@]}"; do test -f "$source_dir/$file"; done
check_hash() {
  local file=$1 expected=$2 actual
  actual=$(sha256sum "$app/$file" | cut -d ' ' -f1)
  if [ "$actual" != "$expected" ]; then
    printf 'Preflight stopped: unexpected installed file %s (revision %s). No files changed.\n' "$file" "$old" >&2
    exit 1
  fi
}
# Baseline: previously deployed teacher-content release. Preserve PWA files.
check_hash accounts/templates/accounts/student_dashboard.html 2db5570ab1155cfc7d8aa6a1af960407fc4a88dd3cd71e4460be8211ddcbd2f8
check_hash accounts/views.py 273eca7933ed1416d9ceddc72df1f4c5b443550fa60f75506bb058adb71037c0
check_hash dashboard/crud.py 160981e50422e5c434a061dc94500a6fb712a373990c07e931341337987fcaf1
check_hash dashboard/forms.py 00f93959cecc6e8f330b2f5ccfe558a6912fd534c8b6dc9f40fb821ffaa6fdb0
check_hash dashboard/templates/dashboard/form.html 25dcb2885810b8c67092581239943b650eb943f131e43f5a60eeca657e8b46c2
check_hash dashboard/templates/dashboard/report_card_list.html 54aefc47376cb54db6627a69e39218cc5402208b0acbe695c87098e58acbe455
test ! -e "$app/dashboard/templates/dashboard/report_card_classes.html"
test ! -e "$app/dashboard/templates/dashboard/report_card_students.html"
check_hash dashboard/urls.py 325ca02691b5c8366289fb1bb153f00674ab613de7f3a671c3ddb3d75dd17a96
check_hash reports/admin.py ad39be1af610eeecd6bc3334a3789d0becaa77b75a8173cedc324f3ed82e0edb
check_hash reports/models.py 8f25bdbc0215a2ec34e1f8993dc1f804a8708efefbc412f3a6160a19d4030eb4
check_hash reports/views.py 6618a27030e00fe53bb51285a58788013f6e30993d200d47498f2ffca8d003b3
test ! -e "$app/reports/migrations/0002_alter_studentreportcard_file_and_more.py"
test ! -e "$app/static/js/report-student-search.js"
mkdir -p /srv/rsp-backups
backup=$(mktemp -d /srv/rsp-backups/report-cards-XXXXXXXX)
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
installed=false
rollback() {
  code=$?
  trap - ERR
  set +e
  systemctl stop rsp
  if [ "$installed" = true ]; then
    # Reverse only this feature's schema while new source is still installed.
    # Old title/file columns are retained, so existing cards survive reversal.
    if ! django migrate reports 0001 --noinput; then
      printf 'Schema rollback failed; service left stopped. Backup: %s\n' "$backup" >&2
      exit "$code"
    fi
  fi
  while IFS= read -r file; do cp -a "$backup/files/$file" "$app/$file"; done < "$backup/existing.txt"
  while IFS= read -r file; do rm -f "$app/$file"; done < "$backup/new.txt"
  cp -a "$backup/revision" "$app/.deployment-revision"
  django collectstatic --noinput
  systemctl start rsp
  printf 'Deployment failed; previous schema/files restored. Backup: %s\n' "$backup" >&2
  exit "$code"
}
trap rollback ERR
systemctl stop rsp
export RSP_REPORT_BACKUP_PATH="$backup/database.dump"
django shell -c '
import os, subprocess
from django.conf import settings
config = settings.DATABASES["default"]
assert "postgresql" in config["ENGINE"], "PostgreSQL expected"
env = os.environ.copy()
env["PGPASSWORD"] = str(config.get("PASSWORD") or "")
command = ["pg_dump", "--format=custom", "--file", os.environ["RSP_REPORT_BACKUP_PATH"]]
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
installed=true
django migrate reports --noinput
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
curl --fail --silent --show-error --connect-timeout 3 --max-time 10 \
  --resolve rsp.roshangaran-elementary.com:443:127.0.0.1 \
  https://rsp.roshangaran-elementary.com/static/js/report-student-search.js -o "$backup/search.js"
cmp "$source_dir/static/js/report-student-search.js" "$backup/search.js"
printf '%s\n' "$new" > "$app/.deployment-revision"
trap - ERR
printf 'Report cards deployed: %s\nBackup: %s\nHTTP %s\n' "$new" "$backup" "$status"

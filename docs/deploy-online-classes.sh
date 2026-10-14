#!/usr/bin/env bash
# Run as root: bash docs/deploy-online-classes.sh SOURCE_DIR NEW_REVISION
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
test -x "$py"
systemctl is-active --quiet rsp

files=(
  dashboard/templates/dashboard/online_class_manage_list.html
  templates/components/sidebar.html
  dashboard/crud.py
  dashboard/forms.py
  dashboard/urls.py
  dashboard/templates/dashboard/bbb_config_list.html
  dashboard/templates/dashboard/form.html
  online_classes/services.py
  online_classes/views.py
  online_classes/templates/online_classes/online_class_list.html
  static/js/online-class-students.js
  online_classes/management/__init__.py
  online_classes/management/commands/__init__.py
  online_classes/management/commands/check_bbb.py
)

for file in "${files[@]}"; do test -f "$source_dir/$file"; done

# Verify the deployed files match the reviewed baseline (main and PWA share these files).
test "$(sha256sum "$app/dashboard/crud.py" | cut -d " " -f1)" = "d2f500f9fd0c33b06891fda5e8e603790c2bc076b29cab59cf9cbe6bc996e89e"
test "$(sha256sum "$app/dashboard/forms.py" | cut -d " " -f1)" = "23b33cf7cbc865dac657f9408ac060e897fe320814acf5beb873d2d3b0ff5e61"
test "$(sha256sum "$app/dashboard/urls.py" | cut -d " " -f1)" = "28f8d79abd3c70b7d7396d13f0441fa297366b6377910452b0d3df0f9b6f0c00"
test "$(sha256sum "$app/dashboard/templates/dashboard/bbb_config_list.html" | cut -d " " -f1)" = "3db98fc5492c9fc4c1a10c4e513b0d1a8b39ced079dfa46b519d1895080663d8"
test "$(sha256sum "$app/dashboard/templates/dashboard/form.html" | cut -d " " -f1)" = "1c8db94bb55d546f91fd8077d357229d25ee9e0c8863f5652b64821666f36c28"
test "$(sha256sum "$app/online_classes/services.py" | cut -d " " -f1)" = "6229168c7b1186f3d0f535e566b9f574e7da7da7a61766b0c0cae0674cb94462"
test "$(sha256sum "$app/online_classes/views.py" | cut -d " " -f1)" = "ce8966d0f2b45fd00aeb2392f940daebb71199b16c0c0411abe4fae79393c433"
test "$(sha256sum "$app/online_classes/templates/online_classes/online_class_list.html" | cut -d " " -f1)" = "76568372aab26f246db37c1c63c120531507a9f0bfd50d55d1b4f6ccf45700d8"

test "$(sha256sum "$app/templates/components/sidebar.html" | cut -d " " -f1)" = "43adbe841a9f4061231c314398cc02788f0efed16125e54e435c7a5fe4762c9a"

test "$(sha256sum "$app/dashboard/templates/dashboard/online_class_manage_list.html" | cut -d " " -f1)" = "da869705938ff4c0ff25ac391491eb00ae73a8e470b4b9c2b8604d5e7967725a"

backup=$(mktemp -d /srv/rsp-backups/online-classes-XXXXXXXX)
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
printf 'Online classes deployed: %s\nBackup: %s\nHTTP %s\n' "$new" "$backup" "$status"

# Network/API failures are reported separately; they do not undo the UI/access fixes.
if ! django check_bbb; then
  printf 'BBB connection could not be verified. Review API URL/secret/network in BBB settings.\n' >&2
fi

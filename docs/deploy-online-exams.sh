#!/usr/bin/env bash
# First installation only. Run as root with an extracted reviewed source tree.
set -Eeuo pipefail
app=/srv/rsp
source_dir=$(realpath "${1:?source directory required}")
new=${2:?commit SHA required}
py=$app/venv/bin/python
test "$EUID" -eq 0
[[ "$new" =~ ^[0-9a-f]{40}$ ]]
test -x "$py"
test -f "$app/.deployment-revision"
test ! -e "$app/online_exams"
test ! -e /etc/systemd/system/rsp-exam-finalize.service
test ! -e /etc/systemd/system/rsp-exam-finalize.timer
command -v pg_dump >/dev/null
systemctl is-active --quiet rsp

# Refuse to overwrite server-only changes or a different baseline.
"$py" - "$app" "$source_dir" <<'PY'
import hashlib, json, pathlib, sys
app, source = map(pathlib.Path, sys.argv[1:])
for name, expected in json.loads((source / 'docs/online-exams-baseline.json').read_text()).items():
    path = app / name
    assert path.is_file(), f'Missing baseline file: {name}'
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == expected, f'Server file differs from reviewed baseline: {name}; stop and review the diff.'
assert (source / 'online_exams/migrations/0001_initial.py').is_file()
assert (source / 'online_exams/fonts/DejaVuSans.ttf').is_file()
PY

runtime_user=$(systemctl show rsp --property=User --value)
runtime_user=${runtime_user:-root}
runtime_group=$(id -gn "$runtime_user")
mkdir -p /srv/rsp-backups
backup=$(mktemp -d /srv/rsp-backups/online-exams-XXXXXXXX)
chmod 700 "$backup"
files=(requirements.txt rsp/settings.py rsp/urls.py templates/components/sidebar.html)
for file in "${files[@]}"; do
  mkdir -p "$backup/files/$(dirname "$file")"
  cp -a "$app/$file" "$backup/files/$file"
done
cp -a "$app/.deployment-revision" "$backup/revision"
"$py" -m pip freeze > "$backup/packages.txt"

django() (
  set -a
  source /etc/rsp/rsp.env
  set +a
  cd "$app"
  "$py" manage.py "$@" --settings=rsp.settings_prod
)

rollback() {
  code=$?
  trap - ERR
  set +e
  systemctl disable --now rsp-exam-finalize.timer
  systemctl stop rsp-exam-finalize.service rsp
  rm -f /etc/systemd/system/rsp-exam-finalize.service /etc/systemd/system/rsp-exam-finalize.timer
  systemctl daemon-reload
  for file in "${files[@]}"; do cp -a "$backup/files/$file" "$app/$file"; done
  # Retain the module as a recovery copy; never delete private uploaded files.
  if [ -d "$app/online_exams" ]; then mv "$app/online_exams" "$backup/failed-online_exams"; fi
  cp -a "$backup/revision" "$app/.deployment-revision"
  systemctl start rsp
  printf 'Deployment failed; previous application files restored. Backup: %s\n' "$backup" >&2
  printf 'Additive exam tables and new dependencies are retained; no existing data was rolled back.\n' >&2
  exit "$code"
}
trap rollback ERR

# Add only the two new dependencies; do not upgrade existing application packages.
"$py" -m pip install 'latex2mathml==3.81.1' 'pypdf==7.0.0'
"$py" -c 'from PIL import features; assert features.check("raqm"), "Pillow needs libraqm for Persian reports"'
systemctl stop rsp
export RSP_EXAM_BACKUP="$backup/database.dump"
django shell -c '
import os, subprocess
from django.conf import settings
config = settings.DATABASES["default"]
assert "postgresql" in config["ENGINE"], "PostgreSQL expected"
env = os.environ.copy(); env["PGPASSWORD"] = str(config.get("PASSWORD") or "")
command = ["pg_dump", "--format=custom", "--file", os.environ["RSP_EXAM_BACKUP"]]
for key, option in [("HOST", "--host"), ("PORT", "--port"), ("USER", "--username")]:
    if config.get(key): command += [option, str(config[key])]
command += [str(config["NAME"])]
subprocess.run(command, env=env, check=True)
'
test -s "$backup/database.dump"
for file in "${files[@]}"; do cp "$source_dir/$file" "$app/$file"; done
cp -a "$source_dir/online_exams" "$app/online_exams"
chown -R "$runtime_user:$runtime_group" "$app/online_exams"
install -d -m 700 -o "$runtime_user" -g "$runtime_group" "$app/private_exam_files"
django migrate online_exams --noinput
django check --deploy
django collectstatic --noinput

cat > /etc/systemd/system/rsp-exam-finalize.service <<EOF
[Unit]
Description=Finalize RSP online exams and generate missing reports
After=network.target
[Service]
Type=oneshot
User=$runtime_user
Group=$runtime_group
WorkingDirectory=/srv/rsp
EnvironmentFile=/etc/rsp/rsp.env
ExecStart=/srv/rsp/venv/bin/python /srv/rsp/manage.py finalize_exams --settings=rsp.settings_prod
UMask=0077
EOF
cat > /etc/systemd/system/rsp-exam-finalize.timer <<'EOF'
[Unit]
Description=Finalize expired RSP exams every minute
[Timer]
OnCalendar=*-*-* *:*:00
Persistent=true
Unit=rsp-exam-finalize.service
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl start rsp-exam-finalize.service
systemctl enable --now rsp-exam-finalize.timer
systemctl start rsp
healthy=false
for attempt in {1..10}; do
  status=$(curl --connect-timeout 3 --max-time 5 -ksS -o /dev/null -w '%{http_code}' \
    --resolve rsp.roshangaran-elementary.com:443:127.0.0.1 \
    https://rsp.roshangaran-elementary.com/exams/ || true)
  if [[ "$status" == 302 || "$status" == 200 ]]; then healthy=true; break; fi
  sleep 1
done
test "$healthy" = true
printf '%s\n' "$new" > "$app/.deployment-revision"
trap - ERR
printf 'Online exams installed: %s\nBackup: %s\nHTTP: %s\n' "$new" "$backup" "$status"

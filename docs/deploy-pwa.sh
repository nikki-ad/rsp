#!/usr/bin/env bash
# Run as root: bash docs/deploy-pwa.sh SOURCE_DIR NEW_REVISION
set -Eeuo pipefail

app=/srv/rsp
source_dir=$(realpath "${1:?source directory required}")
new=${2:?new revision required}
old=6db1f6c48e5cdbc6364006114b2aca50828e84c0
py=$app/venv/bin/python
test "$EUID" -eq 0
mkdir -p /srv/rsp-backups
[[ "$new" =~ ^[0-9a-f]{40}$ ]]
test "$(cat "$app/.deployment-revision")" = "$old"
test -x "$py"
systemctl is-active --quiet rsp

files=(
  rsp/pwa.py
  rsp/urls.py
  static/pwa/icon-192.png
  static/pwa/icon-512.png
  templates/auth_base.html
  templates/base.html
  core/test_content_descriptions.py
)

for file in "${files[@]}"; do test -f "$source_dir/$file"; done

backup=$(mktemp -d /srv/rsp-backups/pwa-XXXXXXXX)
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
# Verify real HTTPS routes and install assets before recording success.
probe="$backup/http-checks"
mkdir -p "$probe"
base=https://rsp.roshangaran-elementary.com
fetch() {
  curl --fail --silent --show-error --connect-timeout 5 --max-time 15 \
    --resolve rsp.roshangaran-elementary.com:443:127.0.0.1 \
    "$base/$1" -o "$probe/$2"
}
fetch manifest.webmanifest manifest.json
fetch sw.js sw.js
fetch accounts/login/ login.html
fetch static/pwa/icon-192.png icon-192.png
fetch static/pwa/icon-512.png icon-512.png
"$py" - "$probe" <<'PYVERIFY'
import json, sys
from pathlib import Path
probe = Path(sys.argv[1])
manifest = json.loads((probe / "manifest.json").read_text())
assert manifest["start_url"] == "/dashboard/"
assert manifest["scope"] == "/" and manifest["display"] == "standalone"
assert len(manifest["icons"]) == 2
worker = (probe / "sw.js").read_text()
assert "self.addEventListener('install'" in worker
assert "caches." not in worker and "addEventListener('fetch'" not in worker
login = (probe / "login.html").read_text()
assert '/manifest.webmanifest' in login and '/sw.js' in login
for filename in ['icon-192.png', 'icon-512.png']:
    assert (probe / filename).read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
print("HTTPS PWA routes, login integration and icons verified")
PYVERIFY
printf '%s\n' "$new" > "$app/.deployment-revision"
trap - ERR
printf 'PWA enabled on existing RSP and database: %s\nBackup: %s\nHTTP %s\n' "$new" "$backup" "$status"

#!/usr/bin/env bash
# Update an existing online-exams installation without dependencies or migrations.
set -Eeuo pipefail
app=/srv/rsp
source_dir=$(realpath "${1:?source directory required}")
new=${2:?commit SHA required}
py=$app/venv/bin/python
test "$EUID" -eq 0
[[ "$new" =~ ^[0-9a-f]{40}$ ]]
test -x "$py"
test -d "$app/online_exams"
systemctl is-active --quiet rsp
systemctl is-active --quiet rsp-exam-finalize.timer

"$py" - "$app" "$source_dir" <<'PY'
import hashlib, json, pathlib, sys
app, source = map(pathlib.Path, sys.argv[1:])
for name, expected in json.loads((source / "docs/exam-actions-baseline.json").read_text()).items():
    path = app / name
    assert path.is_file(), f"Missing server file: {name}"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, f"Server file differs from baseline: {name}"
    assert (source / name).is_file(), f"Missing update file: {name}"
assert not (app / "online_exams/templates/online_exams/delete_exam.html").exists(), "Update already installed or server differs"
PY

backup=$(mktemp -d /srv/rsp-backups/exam-actions-XXXXXXXX)
chmod 700 "$backup"
mapfile -t files < <("$py" - "$source_dir" <<'PY'
import json, pathlib, sys
print("\n".join(json.loads((pathlib.Path(sys.argv[1]) / "docs/exam-actions-baseline.json").read_text())))
PY
)
extra=online_exams/templates/online_exams/delete_exam.html
test -f "$source_dir/$extra"
for file in "${files[@]}"; do
    mkdir -p "$backup/files/$(dirname "$file")"
    cp -a "$app/$file" "$backup/files/$file"
done
cp -a "$app/.deployment-revision" "$backup/revision"
printf '%s\n' "${files[@]}" > "$backup/files.txt"

rollback() {
    code=$?
    trap - ERR
    set +e
    systemctl stop rsp-exam-finalize.timer rsp-exam-finalize.service rsp
    for file in "${files[@]}"; do cp -a "$backup/files/$file" "$app/$file"; done
    rm -f "$app/$extra"
    cp -a "$backup/revision" "$app/.deployment-revision"
    systemctl start rsp
    systemctl start rsp-exam-finalize.timer
    printf 'Update failed; previous files restored. Backup: %s\n' "$backup" >&2
    exit "$code"
}
trap rollback ERR

systemctl stop rsp-exam-finalize.timer
systemctl stop rsp-exam-finalize.service
systemctl stop rsp
for file in "${files[@]}" "$extra"; do
    cp "$source_dir/$file" "$app/$file"
done
runtime_user=$(systemctl show rsp --property=User --value)
runtime_user=${runtime_user:-root}
runtime_group=$(id -gn "$runtime_user")
chown "$runtime_user:$runtime_group" "$app/$extra"

(
    set -a
    source /etc/rsp/rsp.env
    set +a
    cd "$app"
    "$py" manage.py check --deploy --settings=rsp.settings_prod
)
systemctl start rsp
healthy=false
for attempt in {1..10}; do
    status=$(curl --connect-timeout 3 --max-time 5 -ksS -o /dev/null -w '%{http_code}' \
        --resolve rsp.roshangaran-elementary.com:443:127.0.0.1 \
        https://rsp.roshangaran-elementary.com/exams/ || true)
    if [[ "$status" == 200 || "$status" == 302 ]]; then healthy=true; break; fi
    sleep 1
done
test "$healthy" = true
systemctl start rsp-exam-finalize.timer
systemctl is-active --quiet rsp
systemctl is-active --quiet rsp-exam-finalize.timer
printf '%s\n' "$new" > "$app/.deployment-revision"
trap - ERR
printf 'Exam edit/delete update installed: %s\nBackup: %s\nHTTP: %s\n' "$new" "$backup" "$status"

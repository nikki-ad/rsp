# Online exams

This app adds `/exams/` and a sidebar entry for every existing role. Students can
only access their assigned published exams; non-students manage their own exams,
while school managers and super administrators manage all exams and both purge actions.
Teacher audience selection is limited to their active-year classrooms/language groups.

## Behavior

- Wizard: subject/settings/audience → PDF upload or typed questions/options → key → preview → publish.
- Expandable class/group selection, select-all, individual exclusion, unique student counts.
- Draft settings/questions/key remain editable. Publication freezes content, audience, key and timing.
- Typed questions use escaped lightweight markup (`**bold**`, `__italic__`) and
  LaTeX inside `\( ... \)`, converted locally to sanitized native MathML.
  The editor offers fraction, power, radical and preview buttons for every field.
  No external editor service or CDN is needed.
- Each student has one attempt. The deadline is
  `min(started_at + duration, closes_at)`, checked on the server for every write.
  At the exact deadline late answers are rejected and existing saved answers graded.
- Selecting/clearing an answer saves that question immediately. A serialized client
  queue retries transient failures; pending changes stay in the current tab's
  session storage across reloads. Saving is explicitly confirmed in the UI.
  An answer that never reaches the server before the deadline cannot count.
- Closing a browser does not pause time. The management command finalizes expired
  attempts and retries missing reports. Results are also finalized on access.
- Equal question weights. No negative marking: `100 * correct / total`.
  Negative marking: `100 * (correct - wrong/3) / total`. Blanks have no penalty;
  percentages may be negative and are rounded to two decimals.
- Students see a persistent HTML result, not a downloadable report. The optional
  delayed-key setting hides the key column until the window closes; aggregate
  scores and correct/wrong statuses are immediate.
- Managers get Persian PNG report files and a ZIP download. UUID filenames prevent
  duplicate names and archive path injection; each report includes the student's name.
  The PNG contains the answer/key comparison, not the full question text.
- Non-starters are absent only once the window closes.
- Both purge actions require school-manager/superadmin permissions, an explicit
  confirmation page, and a closed window. File-only purge retains student results;
  full purge clears answers/scores/files. A minimal participation tombstone prevents
  retakes; removing result files never silently regenerates them.
- All visible dates/inputs are Jalali, using existing project helpers and Tehran time.

## Private files and dependencies

`private_exam_files/` is deliberately **outside MEDIA_ROOT**. Do not expose it via
nginx, a public storage bucket, or a static alias. Include it in server backups
alongside the PostgreSQL database. Deletion affects active storage; any existing
backups retain their own retention policy.

Dependencies added: `latex2mathml==3.81.1`, `pypdf==7.0.0`. Existing Pillow must have
libraqm support (the deployment script checks this). DejaVu Sans is bundled with
its license for stable Persian rendering without system font installation.

`python manage.py finalize_exams` must run every minute. The provided first-install
script installs a systemd timer with the same user as the existing RSP service and
loads `/etc/rsp/rsp.env` through systemd.

## Local verification

Use the project's Python/Django versions:

```sh
python manage.py migrate
python manage.py check
python manage.py test online_exams
python manage.py test
python manage.py makemigrations --check --dry-run
node --check online_exams/static/online_exams/take.js
```

The regression tests cover hard deadlines, scoring, resumability, persistent
results, delayed keys, class and language-teacher scoping, unauthorized actions,
CSRF, PDF content checks, MathML escaping, report generation and both purge modes.

## Deployment and recovery

`docs/deploy-online-exams.sh SOURCE_DIR COMMIT_SHA` is a **first-install script for
the reviewed feature/pwa baseline**, not a general main/PWA synchronization script.
It compares existing server integration files with `online-exams-baseline.json`
before writing anything. A mismatch requires reviewing the actual server diff.

The script backs up affected files, the old revision, installed package versions
and PostgreSQL; installs only the new dependencies; applies only the new app's
additive migration; collects static files; installs the timer; and checks the
authenticated exam route. It does not merge branches or publish a deployment itself.

On failure it restores application files and disables/removes the new timer.
New dependencies and additive exam tables are retained; no pre-existing data is
replaced or dropped automatically. Private files are never removed by rollback.
For a later manual rollback: stop the timer and app, restore the four backed-up
integration files and revision, move the app module aside, then restart the app.
Keep database/private-file backups until the deployment is accepted. Restoring a
whole database is a separate, explicitly authorized recovery operation.

Production acceptance still requires checking the real service user, filesystem
permissions, timer result, PostgreSQL behavior and browser flows on that server.

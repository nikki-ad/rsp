# Upload progress for teacher content and announcements

Enabled only for creation/editing of teacher assignments, educational materials
(both class and global entry points), language teacher assignments/materials, and
school announcements. Other generic forms and student submission forms keep
their current behavior.

The browser sends one multipart POST with the existing CSRF field and an
`X-RSP-Upload: 1` header. `XMLHttpRequest.upload` supplies actual request-body
progress (combined attachments plus form data). At 100%, the UI waits for the
view to finish saving and return an explicit JSON success response. The view
adds the flash message `با موفقیت انجام شد.` for the destination page, including
ordinary non-JavaScript submissions.

Invalid forms return 422 with field errors, retaining the selected files and
entered values. Network failures, 413, 403, server errors and expired sessions
never count as success. Ambiguous failures advise checking the destination list
before manually retrying. Automatic retries are deliberately absent because
the server may have saved a record before the connection failed.

Submit controls and fields are disabled during the request. Accessibility
includes a labeled progressbar, live status, invalid-field markers, RTL/Persian
digits and reduced-motion CSS.

## Validation

```bash
python manage.py test core.test_upload_progress core.test_uploads_and_dates core.test_workflow_updates notifications.test_announcements language_unit.tests --noinput
node --check static/js/upload-progress.js
NODE_PATH="$CODEX_PRIMARY_RUNTIME_NODE_MODULES" node tests/upload-progress.cjs
bash -n docs/deploy-upload-progress.sh
```

The browser test optionally accepts `CHROMIUM_EXECUTABLE_PATH` to use an existing
Chromium installation. It exercises deterministic upload progress/events,
server confirmation, double submit, invalid data/retry, multipart CSRF and
files, expired login, error responses, network abort, text-only saving and
mobile width. Django tests verify persistence, permissions, CSRF, native POSTs
and creation/editing across the enabled routes.

## Production

No migrations, dependency updates, Nginx settings or database changes are
required. `deploy-upload-progress.sh` takes a downloaded source directory and
its immutable revision, checks the existing production revision, backs up the
13 affected application files, runs deployment checks/collectstatic, and
restarts the existing service. A failed check restores the previous files and
revision. It is intended for main production only; PWA remains a separate
branch and deployment.

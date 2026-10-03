# Uploads, Jalali dates and announcement recipients

Assignments now expose separate document, image and video inputs. Students can download each attachment from their dashboard, assignment list and submission page. Download routes verify active class enrollment; language routes verify active group membership. Missing attachments return 404 instead of a server error.

Educational materials in both school and language units support image and video content types. Videos have a 20 × 1024 × 1024 byte limit. The limit is enforced on the server, including videos submitted through the generic file input. Dedicated video fields accept MP4, WebM, MOV, M4V, AVI, MKV and 3GP; MP4/WebM are recommended for browser compatibility. Image uploads are validated as images.

Student announcements require one or more active classes. Teacher announcements require one or more active teachers. All sends to active student and teacher accounts, including students without an enrollment. Hidden irrelevant recipient selections are cleared by the server. The previous single-class and unrestricted student/teacher announcements retain their historical audience until edited. Editing a historical announcement requires selecting its recipients under the new rules.

Dashboard visibility and notification recipients share the same rules. Recipient changes and deactivation reconcile existing notifications. Scheduled announcements appear at or after their publication time, and their notifications are created when recipients next open their dashboard or notification list. Existing announcements with missing notifications are repaired the same way. Delivery receipts prevent manually deleted notifications from reappearing on each page visit. There is no background scheduler in this change.

Dates display in the Jalali calendar in dashboards, messages, activity logs, reports, announcements and Django admin. Birth dates, academic year dates, cafeteria week dates and announcement publication times accept Jalali input with Persian, Arabic or Latin digits. Example: `1405/07/11 18:30`. ISO Gregorian input is retained for compatibility with existing integrations. Database date/time storage and Tehran timezone are preserved.

## Deployment

This change has not been installed on the production host by the coding environment.

1. Verify `/srv/rsp/.deployment-revision`, the service status and the effective Nginx configuration. Expected previous production revision: `6ea9cc0c1788c0bc99727c1624db535a19aa3934`.
2. Back up application files and PostgreSQL before deploying. Preserve environment settings and uploaded media.
3. Install the pinned requirements using `/srv/rsp/venv/bin/python -m pip install -r requirements.txt`. The additional packages are `jdatetime==5.2.0` and its `jalali-core` dependency.
4. Ensure the HTTPS application's effective `client_max_body_size` allows a complete multipart request containing a 20 MiB video plus other attachments. `64m` is a suitable request ceiling; the application still limits each video to 20 MiB. Check nested location overrides before changing Nginx, run `nginx -t`, then reload.
5. With the service stopped, install the changed code, load `/etc/rsp/rsp.env`, run `manage.py migrate --noinput`, `manage.py collectstatic --noinput` and `manage.py check --deploy`. Record the installed commit in `.deployment-revision`, then restart `rsp`.
6. Verify the service, HTTPS login redirect, a real teacher upload and enrolled-student download. Verify student/class, teacher and all announcement audiences with selected and excluded accounts.

The new migrations add optional assignment attachments and announcement recipient/receipt relations; they preserve existing content and enrollments. Old model choices for single-class announcements are retained for compatibility.

Validation: Django system checks, migration consistency and full regression suite, including upload/download authorization, 20 MiB boundary, Jalali leap-day conversion, Tehran datetime conversion, announcement isolation, recipient edits, scheduled delivery, legacy audiences and notification deletion.

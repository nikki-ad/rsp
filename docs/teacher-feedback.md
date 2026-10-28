# Teacher replies to assignment submissions

School teachers use the existing evaluation page; language assignment owners use
an equivalent reply page. Both support text, file, image, and video, including an
optional caption with every attachment. Existing school evaluations and text
feedback are preserved. Teachers can edit their reply. Text mode disables the
upload control and clears the reply attachment reference server-side.

Students see a compact, collapsed reply on their school assignment list/dashboard
and language dashboard. Attachments download through ownership and active
membership checks. Only the assignment's teacher can write; managers retain
read-only response access. Saving sends a notification to the submitting student.
Image uploads are validated as images; video uploads are limited to 20 MiB,
including videos submitted through the generic file option.

## Deployment

Run `sudo bash docs/deploy-teacher-feedback.sh SOURCE_DIRECTORY REVISION` from a
source archive of the chosen revision. It supports the reviewed web and PWA
baselines and refuses mismatched server files before stopping the service.
It backs up files and PostgreSQL, applies additive migrations, collects static
files, restarts, and checks the local HTTPS dashboard. On failure it restores the
old files and revision. Additive database columns are retained during rollback;
old code ignores them, preserving existing data. The script changes no PWA shell
or service-worker files. Previously stored attachment bytes are not deleted when
replacing/removing a reply attachment.

## Validation

New tests cover both teacher types, all four content modes, captions, editing,
text-mode attachment removal, invalid media, upload limits, notifications, async
responses, old evaluation-only behavior, student privacy, teacher ownership,
manager read access, and archived-year access restrictions.

The existing test
`language_unit.test_teacher_isolation.LanguageTeacherIsolationTests.test_school_online_and_classroom_lookup_are_blocked`
already fails on the base online-class revision `00b2d0b` because it expects HTTP
403 while the updated online-class route returns HTTP 200. This was reproduced
in a clean baseline worktree and is unrelated to assignment feedback.

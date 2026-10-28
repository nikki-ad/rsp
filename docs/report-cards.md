# Report cards

Managers create a report-card title (for example «کارنامه ماهیانه مهر») and choose its academic year under **کارنامه‌ها → ساخت عنوان کارنامه**. The upload form selects that title and accepts PDF, JPG/JPEG, PNG and WebP files. Type a student name and select a result; class/year and username distinguish matching names. Arabic/Persian letter variants are normalized. Saving keeps the period selected and clears the student for the next upload.

The management browser follows title → classroom → enrolled students. Missing uploads are visible; existing files have authenticated download, edit and delete actions. Uploads for students without an active enrollment in the period's year remain accessible under the separate unassigned-students link. Students see only their active files grouped under the title, with a download button.

## Deployment

After merging and updating the existing installation, use its normal environment and settings:

```sh
python manage.py migrate
python manage.py collectstatic --noinput
```

Restart the application using the existing deployment procedure. No new runtime dependency is required.

Migration `reports.0002` groups existing files by their old title without deleting files or duplicate records. Since the historical schema did not record academic year, these groups initially have no year and their files appear under the unassigned link. Edit each historical title to select the correct year; classes then come from enrollments for that year. The old per-file title column remains for safe rollback.

## Validation

`python manage.py test reports dashboard accounts --noinput`: 44 tests pass, including migration/backfill, supported extensions, repeated upload, duplicate prevention, editing, navigation, missing/unassigned uploads, ownership and manager permissions. Django system checks and migration drift checks pass.

A DOM interaction check with 400 student records passes for Persian/Arabic letter normalization, keyboard and button selection, result limiting, stale-selection clearing and required selection. A real browser check could not run because the browser download was unavailable; iPhone/Safari device behavior still needs deployment QA.

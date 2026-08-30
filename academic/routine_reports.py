from datetime import datetime, time, timedelta

from django.db.models import Prefetch
from django.utils import timezone

from .models import Enrollment, StudentDailyRoutine


REPORT_DAYS = 7


def _duration_minutes(start, end):
    start_dt = datetime.combine(datetime.min.date(), start)
    end_dt = datetime.combine(datetime.min.date(), end)
    return int((end_dt - start_dt).total_seconds() // 60)


def _sleep_minutes(value):
    minutes = value.hour * 60 + value.minute
    # Sleep entries shortly after midnight belong to the end of the evening.
    return minutes + 24 * 60 if value.hour < 6 else minutes


def _format_minutes(value):
    if value is None:
        return "—"
    hours, minutes = divmod(round(value), 60)
    return f"{hours} ساعت و {minutes} دقیقه" if hours else f"{minutes} دقیقه"


def _format_clock(value):
    if value is None:
        return "—"
    value = round(value) % (24 * 60)
    hours, minutes = divmod(value, 60)
    return f"{hours:02d}:{minutes:02d}"


def classroom_routine_report(classroom, *, days=REPORT_DAYS):
    today = timezone.localdate()
    start_date = today - timedelta(days=days - 1)
    routine_qs = StudentDailyRoutine.objects.filter(
        record_date__range=(start_date, today),
    ).order_by("record_date")
    enrollments = (
        Enrollment.objects.filter(classroom=classroom, is_active=True)
        .select_related("student__user")
        .prefetch_related(Prefetch("student__daily_routines", queryset=routine_qs, to_attr="report_routines"))
        .order_by("student__user__last_name", "student__user__first_name")
    )

    rows = []
    all_routines = []
    follow_up_count = 0
    for enrollment in enrollments:
        routines = enrollment.student.report_routines
        all_routines.extend(routines)
        study_values = [_duration_minutes(item.study_start, item.study_end) for item in routines]
        homework_values = [_duration_minutes(item.homework_start, item.homework_end) for item in routines]
        sleep_values = [_sleep_minutes(item.sleep_time) for item in routines]
        late_sleep_count = sum(
            1 for item in routines
            if item.sleep_time >= time(23, 0) or item.sleep_time < time(6, 0)
        )

        if len(routines) < 3 or late_sleep_count >= 3:
            status = "follow_up"
            status_label = "نیازمند پیگیری"
            follow_up_count += 1
        elif len(routines) < 5:
            status = "attention"
            status_label = "اطلاعات ناکافی"
        else:
            status = "normal"
            status_label = "روند عادی"

        rows.append({
            "student": enrollment.student,
            "submitted_days": len(routines),
            "study_average": _format_minutes(sum(study_values) / len(study_values) if study_values else None),
            "homework_average": _format_minutes(sum(homework_values) / len(homework_values) if homework_values else None),
            "sleep_average": _format_clock(sum(sleep_values) / len(sleep_values) if sleep_values else None),
            "status": status,
            "status_label": status_label,
        })

    student_count = len(rows)
    study_values = [_duration_minutes(item.study_start, item.study_end) for item in all_routines]
    homework_values = [_duration_minutes(item.homework_start, item.homework_end) for item in all_routines]
    sleep_values = [_sleep_minutes(item.sleep_time) for item in all_routines]
    expected_records = student_count * days

    return {
        "classroom": classroom,
        "start_date": start_date,
        "end_date": today,
        "days": days,
        "student_count": student_count,
        "record_count": len(all_routines),
        "participation_percent": round(len(all_routines) * 100 / expected_records) if expected_records else 0,
        "study_average": _format_minutes(sum(study_values) / len(study_values) if study_values else None),
        "homework_average": _format_minutes(sum(homework_values) / len(homework_values) if homework_values else None),
        "sleep_average": _format_clock(sum(sleep_values) / len(sleep_values) if sleep_values else None),
        "follow_up_count": follow_up_count,
        "rows": rows,
    }

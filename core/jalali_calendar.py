import jdatetime
from django.http import JsonResponse
from django.utils import timezone


def calendar_response(request):
    today = jdatetime.date.fromgregorian(date=timezone.localdate())
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
        if not 1200 <= year <= 1600 or not 1 <= month <= 12:
            raise ValueError
        first = jdatetime.date(year, month, 1)
    except (TypeError, ValueError, OverflowError):
        return JsonResponse({"error": "تاریخ معتبر نیست."}, status=400)
    days = 31 if month <= 6 else 30 if month <= 11 or first.isleap() else 29
    return JsonResponse({"year": year, "month": month, "days": days,
                         "offset": (first.togregorian().weekday() + 2) % 7,
                         "today": today.strftime("%Y/%m/%d")})

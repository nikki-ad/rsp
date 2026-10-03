"""Responses for the explicitly enabled upload forms; ordinary POSTs still work."""

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render


SUCCESS_MESSAGE = "با موفقیت انجام شد."


def upload_success(request, to, **kwargs):
    response = redirect(to, **kwargs)
    messages.success(request, SUCCESS_MESSAGE)
    if request.headers.get("X-RSP-Upload") == "1":
        return JsonResponse({
            "success": True,
            "message": SUCCESS_MESSAGE,
            "redirect_url": response.url,
        })
    return response


def render_upload_form(request, template, context):
    if request.method == "POST" and request.headers.get("X-RSP-Upload") == "1":
        return JsonResponse({
            "success": False,
            "message": "ذخیره انجام نشد؛ موارد مشخص‌شده را اصلاح کنید.",
            "errors": context["form"].errors.get_json_data(),
        }, status=422)
    return render(request, template, {**context, "upload_progress": True})

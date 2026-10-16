from pathlib import Path
from django import forms
from core.uploads import validate_video, VIDEO_EXTENSIONS


class TeacherFeedbackFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["teacher_feedback"].widget = forms.Textarea(attrs={"rows": 4})
        self.fields["teacher_feedback"].help_text = "متن پاسخ یا توضیح پیوست؛ توضیحات همراه فایل هم نمایش داده می‌شود."
        self.fields["feedback_file"].help_text = "برای فیلم حداکثر ۲۰ مگابایت. با انتخاب متن، پیوست قبلی از پاسخ کنار گذاشته می‌شود."

    def clean(self):
        data = super().clean()
        kind = data.get("feedback_type")
        upload = data.get("feedback_file")
        if kind == "text":
            # Text mode must never retain or accept an attachment, including crafted POSTs.
            data["feedback_file"] = False
            if not (data.get("teacher_feedback") or "").strip() and not data.get("evaluation"):
                self.add_error("teacher_feedback", "متن پاسخ معلم را وارد کنید.")
        elif kind in {"file", "image", "video"}:
            changed_kind = self.instance.pk and self.instance.feedback_type != kind
            if not upload or (changed_kind and "feedback_file" not in self.files):
                self.add_error("feedback_file", "پیوست متناسب با نوع پاسخ را انتخاب کنید.")
            elif "feedback_file" in self.files:
                try:
                    if kind == "image":
                        forms.ImageField().clean(upload)
                    if kind == "video" or Path(upload.name).suffix.lower() in VIDEO_EXTENSIONS or getattr(upload, "content_type", "").startswith("video/"):
                        validate_video(upload)
                except forms.ValidationError as error:
                    self.add_error("feedback_file", error)
        return data

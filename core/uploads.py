from pathlib import Path

from django import forms
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404


VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv", ".3gp"}
MAX_VIDEO_SIZE = 20 * 1024 * 1024


def validate_video(upload):
    if upload.size > MAX_VIDEO_SIZE:
        raise ValidationError("حجم فیلم نباید بیشتر از ۲۰ مگابایت باشد.")
    if Path(upload.name).suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValidationError("فرمت فیلم مجاز نیست؛ MP4، WebM، MOV، M4V، AVI، MKV یا 3GP انتخاب کنید.")


class AttachmentFormMixin:
    """Validate both dedicated video uploads and videos uploaded as generic files."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "image" in self.fields:
            self.fields["image"].widget.attrs["accept"] = "image/*"
        if "video" in self.fields:
            self.fields["video"].widget.attrs["accept"] = ",".join(sorted(VIDEO_EXTENSIONS))
            self.fields["video"].help_text = "حداکثر حجم فیلم: ۲۰ مگابایت. برای پخش در مرورگر MP4 یا WebM پیشنهاد می‌شود."

    def clean(self):
        data = super().clean()
        for name in ("file", "video"):
            upload = data.get(name)
            # Only validate new uploads; retain previously stored attachments on edits.
            if upload and name in self.files:
                is_video = name == "video" or Path(upload.name).suffix.lower() in VIDEO_EXTENSIONS
                is_video = is_video or getattr(upload, "content_type", "").startswith("video/")
                if is_video:
                    try:
                        validate_video(upload)
                    except ValidationError as error:
                        self.add_error(name, error)
        return data


class AssignmentContentFormMixin(AttachmentFormMixin):
    """Allow instructions, attachments, or both, but reject empty assignments."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].help_text = (
            "می‌توانید متن تکلیف یا توضیح فایل، عکس و فیلم را اینجا بنویسید. "
            "اگر پیوست دارید، نوشتن توضیحات اختیاری است."
        )

    def clean(self):
        data = super().clean()
        if not (data.get("description") or "").strip() and not any(
            data.get(name) for name in ("file", "image", "video")
        ):
            raise forms.ValidationError("حداقل متن تکلیف یا یک فایل، عکس یا فیلم وارد کنید.")
        return data


def attachment_response(field):
    if not field:
        raise Http404("فایلی برای دریافت وجود ندارد.")
    try:
        stream = field.open("rb")
    except FileNotFoundError:
        raise Http404("فایل در دسترس نیست؛ لطفاً با مسئول سامانه تماس بگیرید.")
    return FileResponse(stream, as_attachment=True, filename=Path(field.name).name)

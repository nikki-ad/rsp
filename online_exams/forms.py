from io import BytesIO

from django import forms
from django.core.exceptions import ValidationError
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from core.jalali import JalaliDateTimeField
from .access import eligible_students
from .models import Exam, Question


class ExamForm(forms.ModelForm):
    opens_at = JalaliDateTimeField(label="شروع بازه مجاز (به وقت تهران)")
    closes_at = JalaliDateTimeField(label="پایان قطعی آزمون (به وقت تهران)")
    students = forms.ModelMultipleChoiceField(queryset=None, label="شرکت‌کنندگان")

    class Meta:
        model = Exam
        fields = ("subject", "title", "mode", "question_pdf", "question_count",
                  "duration_minutes", "opens_at", "closes_at", "negative_marking", "show_key_immediately")

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["students"].queryset = eligible_students(user)
        self.fields["question_pdf"].widget.attrs["accept"] = ".pdf,application/pdf"
        self.fields["question_count"].help_text = "بین ۱ تا ۳۰۰ سؤال؛ همه سؤال‌ها امتیاز برابر دارند."
        self.fields["show_key_immediately"].help_text = "اگر خاموش باشد، کلید پس از پایان بازه نمایش داده می‌شود. درصد بلافاصله قابل مشاهده است."

    def clean_question_pdf(self):
        file = self.cleaned_data.get("question_pdf")
        if not file or not hasattr(file, "temporary_file_path") and not hasattr(file, "content_type"):
            return file
        if file.size > 20 * 1024 * 1024 or not file.name.lower().endswith(".pdf"):
            raise ValidationError("فایل PDF حداکثر ۲۰ مگابایت بارگذاری کنید.")
        data = file.read()
        file.seek(0)
        if not data.startswith(b"%PDF-"):
            raise ValidationError("محتوای فایل PDF معتبر نیست.")
        try:
            reader = PdfReader(BytesIO(data))
            if reader.is_encrypted or not 1 <= len(reader.pages) <= 500:
                raise ValidationError("PDF باید بدون رمز و دارای ۱ تا ۵۰۰ صفحه باشد.")
            root = reader.trailer["/Root"]
            names = root.get("/Names", {})
            if hasattr(names, "get_object"):
                names = names.get_object()
            if ("/OpenAction" in root or "/AA" in root or "/JavaScript" in names or
                    "/EmbeddedFiles" in names or any("/AA" in page for page in reader.pages)):
                raise ValidationError("PDF دارای محتوای فعال یا پیوست داخلی است؛ نسخه چاپی PDF بارگذاری کنید.")
        except (PdfReadError, ValueError, OSError, KeyError, RecursionError):
            raise ValidationError("فایل PDF خوانده نمی‌شود.")
        return file

    def clean(self):
        data = super().clean()
        if data.get("opens_at") and data.get("closes_at") and data["opens_at"] >= data["closes_at"]:
            self.add_error("closes_at", "پایان آزمون باید بعد از شروع باشد.")
        if data.get("mode") == "pdf" and not data.get("question_pdf"):
            self.add_error("question_pdf", "فایل سؤال‌ها را انتخاب کنید.")
        return data


class QuestionForm(forms.ModelForm):
    option1 = forms.CharField(label="گزینه ۱", max_length=3000, widget=forms.Textarea)
    option2 = forms.CharField(label="گزینه ۲", max_length=3000, widget=forms.Textarea)
    option3 = forms.CharField(label="گزینه ۳", max_length=3000, widget=forms.Textarea)
    option4 = forms.CharField(label="گزینه ۴", max_length=3000, widget=forms.Textarea)

    class Meta:
        model = Question
        fields = ("text",)
        labels = {"text": "صورت سؤال"}
        widgets = {"text": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["text"].required = True
        for i, option in enumerate(self.instance.options or [], 1):
            self.fields[f"option{i}"].initial = option
        for field in self.fields.values():
            field.widget.attrs.update({"class": "exam-editor", "rows": 3})

    def save(self, commit=True):
        question = super().save(commit=False)
        question.options = [self.cleaned_data[f"option{i}"] for i in range(1, 5)]
        if commit:
            question.save()
        return question


class KeyForm(forms.Form):
    def __init__(self, *args, questions, **kwargs):
        super().__init__(*args, **kwargs)
        for question in questions:
            self.fields[f"key_{question.number}"] = forms.TypedChoiceField(
                label=f"سؤال {question.number}", coerce=int,
                choices=[("", "انتخاب کنید")] + [(i, str(i)) for i in range(1, 5)],
                initial=question.correct_option)

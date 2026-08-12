from django import forms

from .models import Message


class MessageForm(forms.ModelForm):

    class Meta:
        model = Message

        fields = [
            "text",
            "file",
        ]

        labels = {
            "text": "پیام",
            "file": "فایل",
        }

    def clean(self):
        cleaned_data = super().clean()

        text = cleaned_data.get("text")
        file = cleaned_data.get("file")

        if not text and not file:
            raise forms.ValidationError(
                "حداقل متن پیام یا یک فایل باید ارسال شود."
            )

        return cleaned_data
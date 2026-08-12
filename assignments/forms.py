from django import forms

from .models import Assignment, AssignmentSubmission

class AssignmentCreateForm(forms.ModelForm):

    class Meta:
        model = Assignment

        fields = [
            "title",
            "description",
            "file",
        ]

        labels = {
            "title": "عنوان تکلیف",
            "description": "توضیحات",
            "file": "فایل تکلیف",
        }

class AssignmentSubmissionForm(forms.ModelForm):

    class Meta:
        model = AssignmentSubmission

        fields = [
            "answer_text",
            "file",
        ]

        labels = {
            "answer_text": "متن پاسخ",
            "file": "فایل پاسخ",
        }



class AssignmentEvaluationForm(forms.ModelForm):

    class Meta:
        model = AssignmentSubmission

        fields = [
            "evaluation",
            "teacher_feedback",
        ]

        labels = {
            "evaluation": "ارزیابی توصیفی",
            "teacher_feedback": "بازخورد معلم",
        }
from django import forms
from core.feedback_forms import TeacherFeedbackFormMixin
from core.uploads import AssignmentContentFormMixin

from .models import Assignment, AssignmentSubmission

class AssignmentCreateForm(AssignmentContentFormMixin, forms.ModelForm):

    class Meta:
        model = Assignment

        fields = [
            "title",
            "description",
            "file", "image", "video",
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



class AssignmentEvaluationForm(TeacherFeedbackFormMixin, forms.ModelForm):

    class Meta:
        model = AssignmentSubmission

        fields = [
            "evaluation",
            "feedback_type",
            "teacher_feedback",
            "feedback_file",
        ]

        labels = {
            "evaluation": "ارزیابی توصیفی",
            "teacher_feedback": "بازخورد معلم",
        }

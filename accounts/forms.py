from django import forms
from django.contrib.auth import get_user_model
from accounts.models import StudentProfile
from academic.models import AcademicYear, Classroom, Enrollment
from django.db import transaction



User = get_user_model()


class StudentCreateForm(forms.Form):
    first_name = forms.CharField(
        max_length=150,
        label="نام",
    )

    last_name = forms.CharField(
        max_length=150,
        label="نام خانوادگی",
    )
    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.none(),
        label="سال تحصیلی",
    )

    classroom = forms.ModelChoiceField(
        queryset=Classroom.objects.none(),
        label="کلاس",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["academic_year"].queryset = AcademicYear.objects.filter(
            status="active"
        )

        self.fields["classroom"].queryset = Classroom.objects.none()

        if self.is_bound:
            academic_year_id = self.data.get("academic_year")

            if academic_year_id:
                self.fields["classroom"].queryset = Classroom.objects.filter(
                    academic_year_id=academic_year_id
                ).order_by(
                    "grade__order",
                    "name",
                )


    def generate_username(self):
        first_name = self.cleaned_data["first_name"].strip()
        last_name = self.cleaned_data["last_name"].strip()

        base = f"{first_name}.{last_name}".replace(" ", "").lower()

        username = base
        counter = 1

        while User.objects.filter(username=username).exists():
            username = f"{base}{counter}"
            counter += 1

        return username


    def clean(self):
        cleaned_data = super().clean()

        academic_year = cleaned_data.get("academic_year")
        classroom = cleaned_data.get("classroom")

        if (
            academic_year
            and classroom
            and classroom.academic_year_id != academic_year.id
        ):
            self.add_error(
                "classroom",
                "کلاس انتخاب‌شده متعلق به این سال تحصیلی نیست.",
            )

        if academic_year and classroom:
            enrolled_count = Enrollment.objects.filter(
                classroom=classroom,
                academic_year=academic_year,
                is_active=True,
            ).count()

            if enrolled_count >= classroom.capacity:
                self.add_error(
                    "classroom",
                    "ظرفیت این کلاس تکمیل شده است.",
                )

        return cleaned_data

    def generate_password(self):
        return "12345678"


    @transaction.atomic
    def save(self):
        username = self.generate_username()
        password = self.generate_password()

        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=self.cleaned_data["first_name"].strip(),
            last_name=self.cleaned_data["last_name"].strip(),
        )

        student_profile = StudentProfile.objects.create(
            user=user,
        )

        Enrollment.objects.create(
            student=student_profile,
            academic_year=self.cleaned_data["academic_year"],
            classroom=self.cleaned_data["classroom"],
            is_active=True,
        )

        return user


class TeacherCreateForm(forms.Form):

    first_name = forms.CharField(
        max_length=150,
        label="نام",
    )

    last_name = forms.CharField(
        max_length=150,
        label="نام خانوادگی",
    )

    personnel_code = forms.CharField(
        max_length=20,
        required=False,
        label="کد پرسنلی",
    )

    expertise = forms.CharField(
        max_length=100,
        required=False,
        label="تخصص",
    )


    def generate_username(self):
        first_name = self.cleaned_data["first_name"].strip()
        last_name = self.cleaned_data["last_name"].strip()

        base = f"{first_name}.{last_name}".replace(" ", "").lower()

        username = base
        counter = 1

        while User.objects.filter(username=username).exists():
            username = f"{base}{counter}"
            counter += 1

        return username


    def generate_password(self):
        return "12345678"


    @transaction.atomic
    def save(self):

        username = self.generate_username()
        password = self.generate_password()

        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=self.cleaned_data["first_name"].strip(),
            last_name=self.cleaned_data["last_name"].strip(),
            role="teacher",
        )

        from accounts.models import TeacherProfile

        TeacherProfile.objects.create(
            user=user,
            personnel_code=self.cleaned_data.get("personnel_code"),
            expertise=self.cleaned_data.get("expertise"),
        )

        return user
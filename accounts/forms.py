from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction

from accounts.choices import Role
from accounts.models import StudentProfile, TeacherProfile
from academic.models import AcademicYear, Classroom, Enrollment
from academic.models import TeacherClassAssignment


User = get_user_model()


class StudentCreateForm(forms.Form):
    first_name = forms.CharField(max_length=150, label="نام")
    last_name = forms.CharField(max_length=150, label="نام خانوادگی")
    national_code = forms.CharField(
        max_length=10,
        required=False,
        label="کد ملی",
    )
    birth_date = forms.DateField(
        required=False,
        label="تاریخ تولد",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    guardian_name = forms.CharField(
        max_length=100,
        required=False,
        label="نام ولی",
    )
    guardian_phone = forms.CharField(
        max_length=20,
        required=False,
        label="شماره تماس ولی",
    )
    address = forms.CharField(
        required=False,
        label="آدرس",
        widget=forms.Textarea(attrs={"rows": 3}),
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
            status=AcademicYear.Status.ACTIVE,
        )

        self.fields["classroom"].queryset = Classroom.objects.none()

        if self.is_bound:
            academic_year_id = self.data.get("academic_year")
            if academic_year_id:
                self.fields["classroom"].queryset = Classroom.objects.filter(
                    academic_year_id=academic_year_id,
                ).order_by("grade__order", "name")

    def generate_username(self):
        first_name = self.cleaned_data["first_name"].strip()
        last_name = self.cleaned_data["last_name"].strip()
        base = f"{first_name}.{last_name}".replace(" ", "").lower() or "student"
        username = base
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base}{counter}"
            counter += 1
        return username

    def clean_national_code(self):
        national_code = (self.cleaned_data.get("national_code") or "").strip()
        if not national_code:
            return ""
        if StudentProfile.objects.filter(national_code=national_code).exists():
            raise forms.ValidationError("این کد ملی قبلاً ثبت شده است.")
        return national_code

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
                self.add_error("classroom", "ظرفیت این کلاس تکمیل شده است.")

        return cleaned_data

    def generate_password(self):
        return "12345678"

    @transaction.atomic
    def save(self, created_by=None):
        username = self.generate_username()
        password = self.generate_password()

        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=self.cleaned_data["first_name"].strip(),
            last_name=self.cleaned_data["last_name"].strip(),
            role=Role.STUDENT,
        )

        student_profile = StudentProfile.objects.create(
            user=user,
            national_code=self.cleaned_data.get("national_code") or None,
            birth_date=self.cleaned_data.get("birth_date"),
            guardian_name=self.cleaned_data.get("guardian_name") or "",
            guardian_phone=self.cleaned_data.get("guardian_phone") or "",
            address=self.cleaned_data.get("address") or "",
            created_by=created_by,
        )

        Enrollment.objects.create(
            student=student_profile,
            academic_year=self.cleaned_data["academic_year"],
            classroom=self.cleaned_data["classroom"],
            is_active=True,
            created_by=created_by,
        )
        return user


class TeacherCreateForm(forms.Form):
    first_name = forms.CharField(max_length=150, label="نام")
    last_name = forms.CharField(max_length=150, label="نام خانوادگی")
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
    description = forms.CharField(
        required=False,
        label="توضیحات",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    classrooms = forms.ModelMultipleChoiceField(
        queryset=Classroom.objects.none(),
        required=False,
        label="کلاس‌ها",
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active_year = AcademicYear.objects.filter(
            status=AcademicYear.Status.ACTIVE,
        ).first()
        if active_year:
            self.fields["classrooms"].queryset = Classroom.objects.filter(
                academic_year=active_year,
            ).order_by("grade__order", "name")

    def generate_username(self):
        first_name = self.cleaned_data["first_name"].strip()
        last_name = self.cleaned_data["last_name"].strip()
        base = f"{first_name}.{last_name}".replace(" ", "").lower() or "teacher"
        username = base
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base}{counter}"
            counter += 1
        return username

    def generate_password(self):
        return "12345678"

    def clean_personnel_code(self):
        code = (self.cleaned_data.get("personnel_code") or "").strip()
        if not code:
            return ""
        if TeacherProfile.objects.filter(personnel_code=code).exists():
            raise forms.ValidationError("این کد پرسنلی قبلاً ثبت شده است.")
        return code

    @transaction.atomic
    def save(self, created_by=None):
        user = User.objects.create_user(
            username=self.generate_username(),
            password=self.generate_password(),
            first_name=self.cleaned_data["first_name"].strip(),
            last_name=self.cleaned_data["last_name"].strip(),
            role=Role.TEACHER,
        )

        teacher_profile = TeacherProfile.objects.create(
            user=user,
            personnel_code=self.cleaned_data.get("personnel_code") or None,
            expertise=self.cleaned_data.get("expertise") or "",
            description=self.cleaned_data.get("description") or "",
            created_by=created_by,
        )

        for classroom in self.cleaned_data.get("classrooms") or []:
            TeacherClassAssignment.objects.create(
                teacher=teacher_profile,
                classroom=classroom,
                created_by=created_by,
            )
        return user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "avatar")
        labels = {
            "first_name": "نام",
            "last_name": "نام خانوادگی",
            "email": "ایمیل",
            "avatar": "عکس پروفایل",
        }
        widgets = {
            "avatar": forms.ClearableFileInput(
                attrs={"accept": "image/jpeg,image/png,image/webp"},
            ),
        }

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar and hasattr(avatar, "size") and avatar.size > 5 * 1024 * 1024:
            raise forms.ValidationError("حجم عکس نباید بیشتر از ۵ مگابایت باشد.")
        return avatar


class StudentSelfProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = (
            "national_code",
            "birth_date",
            "guardian_name",
            "guardian_phone",
            "address",
        )
        widgets = {
            "birth_date": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            ),
            "address": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["birth_date"].input_formats = ["%Y-%m-%d"]

    def clean_national_code(self):
        national_code = (self.cleaned_data.get("national_code") or "").strip()
        if not national_code:
            return None
        exists = StudentProfile.objects.filter(
            national_code=national_code,
        ).exclude(pk=self.instance.pk)
        if exists.exists():
            raise forms.ValidationError("این کد ملی قبلاً ثبت شده است.")
        return national_code


class TeacherSelfProfileForm(forms.ModelForm):
    class Meta:
        model = TeacherProfile
        fields = ("personnel_code", "expertise", "description")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_personnel_code(self):
        code = (self.cleaned_data.get("personnel_code") or "").strip()
        if not code:
            return None
        exists = TeacherProfile.objects.filter(personnel_code=code).exclude(
            pk=self.instance.pk,
        )
        if exists.exists():
            raise forms.ValidationError("این کد پرسنلی قبلاً ثبت شده است.")
        return code


class StudentEditForm(forms.Form):
    first_name = forms.CharField(max_length=150, label="نام")
    last_name = forms.CharField(max_length=150, label="نام خانوادگی")
    is_active = forms.BooleanField(required=False, label="حساب فعال است")
    national_code = forms.CharField(
        max_length=10,
        required=False,
        label="کد ملی",
    )
    birth_date = forms.DateField(
        required=False,
        label="تاریخ تولد",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    guardian_name = forms.CharField(
        max_length=100,
        required=False,
        label="نام ولی",
    )
    guardian_phone = forms.CharField(
        max_length=20,
        required=False,
        label="شماره تماس ولی",
    )
    address = forms.CharField(
        required=False,
        label="آدرس",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    classroom = forms.ModelChoiceField(
        queryset=Classroom.objects.none(),
        required=False,
        label="کلاس سال فعال",
    )

    def __init__(self, *args, student=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.student = student
        active_year = AcademicYear.objects.filter(
            status=AcademicYear.Status.ACTIVE,
        ).first()
        self.active_year = active_year
        if active_year:
            self.fields["classroom"].queryset = Classroom.objects.filter(
                academic_year=active_year,
            ).order_by("grade__order", "name")

    def clean_national_code(self):
        national_code = (self.cleaned_data.get("national_code") or "").strip()
        if not national_code:
            return ""
        exists = StudentProfile.objects.filter(
            national_code=national_code,
        ).exclude(pk=self.student.pk)
        if exists.exists():
            raise forms.ValidationError("این کد ملی قبلاً ثبت شده است.")
        return national_code

    def clean_classroom(self):
        classroom = self.cleaned_data.get("classroom")
        if classroom and self.active_year:
            enrolled_count = Enrollment.objects.filter(
                classroom=classroom,
                academic_year=self.active_year,
                is_active=True,
            ).exclude(student=self.student).count()
            if enrolled_count >= classroom.capacity:
                raise forms.ValidationError("ظرفیت این کلاس تکمیل شده است.")
        return classroom

    @transaction.atomic
    def save(self):
        user = self.student.user
        user.first_name = self.cleaned_data["first_name"].strip()
        user.last_name = self.cleaned_data["last_name"].strip()
        user.is_active = bool(self.cleaned_data.get("is_active"))
        user.save(update_fields=["first_name", "last_name", "is_active"])

        self.student.national_code = self.cleaned_data.get("national_code") or None
        self.student.birth_date = self.cleaned_data.get("birth_date")
        self.student.guardian_name = self.cleaned_data.get("guardian_name") or ""
        self.student.guardian_phone = self.cleaned_data.get("guardian_phone") or ""
        self.student.address = self.cleaned_data.get("address") or ""
        self.student.save()

        classroom = self.cleaned_data.get("classroom")
        if self.active_year:
            enrollment = Enrollment.objects.filter(
                student=self.student,
                academic_year=self.active_year,
            ).first()
            if classroom:
                if enrollment:
                    enrollment.classroom = classroom
                    enrollment.is_active = True
                    enrollment.full_clean()
                    enrollment.save()
                else:
                    Enrollment.objects.create(
                        student=self.student,
                        academic_year=self.active_year,
                        classroom=classroom,
                        is_active=True,
                    )
            elif enrollment:
                enrollment.is_active = False
                enrollment.save(update_fields=["is_active", "updated_at"])
        return self.student


class TeacherEditForm(forms.Form):
    first_name = forms.CharField(max_length=150, label="نام")
    last_name = forms.CharField(max_length=150, label="نام خانوادگی")
    is_active = forms.BooleanField(required=False, label="حساب فعال است")
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
    description = forms.CharField(
        required=False,
        label="توضیحات",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    classrooms = forms.ModelMultipleChoiceField(
        queryset=Classroom.objects.none(),
        required=False,
        label="کلاس‌های سال فعال",
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, teacher=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.teacher = teacher
        active_year = AcademicYear.objects.filter(
            status=AcademicYear.Status.ACTIVE,
        ).first()
        self.active_year = active_year
        if active_year:
            self.fields["classrooms"].queryset = Classroom.objects.filter(
                academic_year=active_year,
            ).order_by("grade__order", "name")

    def clean_personnel_code(self):
        code = (self.cleaned_data.get("personnel_code") or "").strip()
        if not code:
            return ""
        exists = TeacherProfile.objects.filter(
            personnel_code=code,
        ).exclude(pk=self.teacher.pk)
        if exists.exists():
            raise forms.ValidationError("این کد پرسنلی قبلاً ثبت شده است.")
        return code

    @transaction.atomic
    def save(self):
        user = self.teacher.user
        user.first_name = self.cleaned_data["first_name"].strip()
        user.last_name = self.cleaned_data["last_name"].strip()
        user.is_active = bool(self.cleaned_data.get("is_active"))
        user.save(update_fields=["first_name", "last_name", "is_active"])

        self.teacher.personnel_code = self.cleaned_data.get("personnel_code") or None
        self.teacher.expertise = self.cleaned_data.get("expertise") or ""
        self.teacher.description = self.cleaned_data.get("description") or ""
        self.teacher.save()

        selected = set(self.cleaned_data.get("classrooms") or [])
        if self.active_year:
            current = TeacherClassAssignment.objects.filter(
                teacher=self.teacher,
                classroom__academic_year=self.active_year,
            )
            current_map = {item.classroom_id: item for item in current}
            selected_ids = {classroom.id for classroom in selected}

            for classroom_id, assignment in current_map.items():
                if classroom_id not in selected_ids:
                    assignment.delete()

            for classroom in selected:
                TeacherClassAssignment.objects.get_or_create(
                    teacher=self.teacher,
                    classroom=classroom,
                )
        return self.teacher

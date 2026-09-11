from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.forms import inlineformset_factory
from django.utils import timezone

from academic.models import AcademicYear, Classroom, Enrollment, Grade
from accounts.models import StudentProfile, TeacherProfile
from notifications.models import Announcement
from online_classes.models import BBBConfiguration, OnlineClass
from reports.models import StudentReportCard
from accounts.choices import Role
from cafeteria.models import CafeteriaMenu, CafeteriaWeek


User = get_user_model()


class GeneralUserForm(forms.ModelForm):
    password1 = forms.CharField(required=False, label="رمز عبور", widget=forms.PasswordInput)
    password2 = forms.CharField(required=False, label="تکرار رمز عبور", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "role", "is_active")
        labels = {
            "username": "نام کاربری",
            "first_name": "نام",
            "last_name": "نام خانوادگی",
            "email": "ایمیل",
            "role": "نقش",
            "is_active": "حساب فعال است",
        }

    def __init__(self, *args, allow_super_admin=False, **kwargs):
        super().__init__(*args, **kwargs)
        allowed_roles = [Role.SCHOOL_MANAGER, Role.FINANCE, Role.OPERATOR]
        if allow_super_admin:
            allowed_roles.insert(0, Role.SUPER_ADMIN)
        self.fields["role"].choices = [
            (value, label) for value, label in Role.choices if value in allowed_roles
        ]
        if not self.instance.pk:
            self.fields["password1"].required = True
            self.fields["password2"].required = True

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1") or ""
        password2 = cleaned_data.get("password2") or ""
        if password1 or password2:
            if password1 != password2:
                self.add_error("password2", "تکرار رمز عبور یکسان نیست.")
            else:
                try:
                    validate_password(password1, self.instance if self.instance.pk else None)
                except DjangoValidationError as exc:
                    self.add_error("password1", exc)
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get("password1"):
            user.set_password(self.cleaned_data["password1"])
        user.is_staff = user.role in {Role.SUPER_ADMIN, Role.SCHOOL_MANAGER, Role.FINANCE}
        if commit:
            user.save()
        return user


class CafeteriaWeekForm(forms.ModelForm):
    class Meta:
        model = CafeteriaWeek
        fields = ("title", "start_date", "is_active")
        widgets = {"start_date": forms.DateInput(attrs={"type": "date"})}

    def clean_is_active(self):
        is_active = self.cleaned_data["is_active"]
        if is_active:
            existing = CafeteriaWeek.objects.filter(is_active=True)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError("ابتدا هفته غذایی فعال فعلی را غیرفعال کنید.")
        return is_active


CafeteriaMenuFormSet = inlineformset_factory(
    CafeteriaWeek,
    CafeteriaMenu,
    fields=("day", "food_name", "description", "price"),
    extra=5,
    max_num=5,
    can_delete=True,
    widgets={"description": forms.Textarea(attrs={"rows": 2})},
)


class AcademicYearForm(forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = (
            "title",
            "status",
            "description",
            "start_date",
            "end_date",
        )
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_status(self):
        status = self.cleaned_data["status"]
        if status == AcademicYear.Status.ACTIVE:
            qs = AcademicYear.objects.filter(status=AcademicYear.Status.ACTIVE)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    "در هر زمان فقط یک سال تحصیلی می‌تواند فعال باشد. "
                    "ابتدا سال فعال فعلی را آرشیو کنید."
                )
        return status


class GradeForm(forms.ModelForm):
    class Meta:
        model = Grade
        fields = ("code", "title", "order", "description")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class ClassroomForm(forms.ModelForm):
    teachers = forms.ModelMultipleChoiceField(
        queryset=TeacherProfile.objects.select_related("user").all(),
        required=False,
        label="معلمان کلاس",
        widget=forms.CheckboxSelectMultiple,
    )

    SCHEDULE_DAYS = (
        ("saturday", "شنبه"),
        ("sunday", "یکشنبه"),
        ("monday", "دوشنبه"),
        ("tuesday", "سه‌شنبه"),
        ("wednesday", "چهارشنبه"),
    )

    class Meta:
        model = Classroom
        fields = (
            "academic_year",
            "grade",
            "name",
            "capacity",
            "description",
            "daily_report_responsible",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["daily_report_responsible"].queryset = (
            TeacherProfile.objects.select_related("user")
            .filter(user__is_active=True)
            .order_by("user__last_name", "user__first_name")
        )
        self.fields["daily_report_responsible"].help_text = (
            "فقط یکی از معلمان انتخاب‌شده همین کلاس را انتخاب کنید. این بخش اختیاری است."
        )

        existing_schedule = {}
        if self.instance.pk and not self.is_bound:
            existing_schedule = {
                (item.day, item.period): item.subject
                for item in self.instance.weekly_schedule.all()
            }

        for day_key, day_label in self.SCHEDULE_DAYS:
            for period in range(1, 6):
                field_name = f"schedule_{day_key}_{period}"
                self.fields[field_name] = forms.CharField(
                    required=False,
                    max_length=100,
                    label=f"{day_label} - زنگ {period}",
                    widget=forms.TextInput(
                        attrs={
                            "class": "schedule-slot-input",
                            "placeholder": "نام درس",
                            "autocomplete": "off",
                        }
                    ),
                )
                if not self.is_bound:
                    self.fields[field_name].initial = existing_schedule.get(
                        (day_key, period),
                        "",
                    )

    def clean(self):
        cleaned_data = super().clean()
        responsible = cleaned_data.get("daily_report_responsible")
        teachers = cleaned_data.get("teachers")
        if responsible and teachers is not None and responsible not in teachers:
            self.add_error(
                "daily_report_responsible",
                "مسئول پیگیری باید در فهرست معلمان همین کلاس انتخاب شده باشد.",
            )
        return cleaned_data

    def save(self, commit=True):
        classroom = super().save(commit=commit)
        schedule_data = {}
        for day_key, _day_label in self.SCHEDULE_DAYS:
            for period in range(1, 6):
                field_name = f"schedule_{day_key}_{period}"
                schedule_data[(day_key, period)] = (
                    self.cleaned_data.get(field_name) or ""
                ).strip()

        if commit:
            classroom.sync_weekly_schedule(schedule_data)
        else:
            classroom._pending_weekly_schedule = schedule_data

        return classroom


class EnrollmentManageForm(forms.ModelForm):
    override_capacity = forms.BooleanField(
        required=False,
        label="تأیید ثبت‌نام بیش از ظرفیت",
        help_text="فقط در شرایط استثنایی این گزینه را فعال کنید.",
    )

    class Meta:
        model = Enrollment
        fields = (
            "student",
            "academic_year",
            "classroom",
            "roll_number",
            "is_active",
        )

    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get("student")
        academic_year = cleaned_data.get("academic_year")
        classroom = cleaned_data.get("classroom")
        is_active = cleaned_data.get("is_active")
        override_capacity = cleaned_data.get("override_capacity")

        if (
            classroom
            and academic_year
            and classroom.academic_year_id != academic_year.id
        ):
            self.add_error(
                "classroom",
                "کلاس انتخاب‌شده متعلق به سال تحصیلی انتخاب‌شده نیست.",
            )

        if student and academic_year and is_active:
            existing = Enrollment.objects.filter(
                student=student,
                academic_year=academic_year,
                is_active=True,
            )
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError(
                    "این دانش‌آموز در این سال تحصیلی یک ثبت‌نام فعال دارد."
                )

        if classroom and is_active:
            active_enrollments = classroom.enrollments.filter(is_active=True)
            if self.instance.pk:
                active_enrollments = active_enrollments.exclude(pk=self.instance.pk)
            if (
                active_enrollments.count() >= classroom.capacity
                and not override_capacity
            ):
                raise forms.ValidationError(
                    "ظرفیت این کلاس تکمیل شده است. "
                    "برای ثبت استثنایی، گزینه تأیید ثبت‌نام بیش از ظرفیت را فعال کنید."
                )

        return cleaned_data


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = (
            "title",
            "message",
            "audience",
            "classroom",
            "publish_at",
            "is_active",
        )
        widgets = {
            "message": forms.Textarea(attrs={"rows": 5}),
            "publish_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["publish_at"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        ]
        self.fields["classroom"].queryset = Classroom.objects.select_related(
            "academic_year",
            "grade",
        )
        if not self.initial.get("publish_at") and not self.instance.pk:
            self.initial["publish_at"] = timezone.localtime().strftime(
                "%Y-%m-%dT%H:%M"
            )

    def clean(self):
        cleaned_data = super().clean()
        audience = cleaned_data.get("audience")
        classroom = cleaned_data.get("classroom")
        if audience == Announcement.Audience.CLASSROOM and not classroom:
            self.add_error(
                "classroom",
                "برای اطلاعیه مخصوص کلاس، انتخاب کلاس الزامی است.",
            )
        if audience != Announcement.Audience.CLASSROOM:
            cleaned_data["classroom"] = None
        return cleaned_data


class ReportCardForm(forms.ModelForm):
    class Meta:
        model = StudentReportCard
        fields = ("student", "title", "file", "is_active")


class BBBConfigurationForm(forms.ModelForm):
    class Meta:
        model = BBBConfiguration
        fields = ("name", "api_url", "secret", "is_active")
        widgets = {
            "secret": forms.PasswordInput(render_value=True),
        }


class OnlineClassForm(forms.ModelForm):
    class Meta:
        model = OnlineClass
        fields = (
            "title",
            "academic_year",
            "provider",
            "bbb_configuration",
            "bbb_room_id",
            "skyroom_url",
            "students",
            "teachers",
            "is_active",
        )
        widgets = {
            "students": forms.CheckboxSelectMultiple,
            "teachers": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        year_id = None
        if self.is_bound:
            year_id = self.data.get("academic_year")
        elif self.instance.pk:
            year_id = self.instance.academic_year_id

        student_qs = StudentProfile.objects.select_related("user")
        teacher_qs = TeacherProfile.objects.select_related("user")
        if year_id:
            student_qs = student_qs.filter(
                enrollments__academic_year_id=year_id,
                enrollments__is_active=True,
            ).distinct()
        self.fields["students"].queryset = student_qs.order_by(
            "user__last_name",
            "user__first_name",
        )
        self.fields["teachers"].queryset = teacher_qs.order_by(
            "user__last_name",
            "user__first_name",
        )

    def clean(self):
        cleaned_data = super().clean()
        provider = cleaned_data.get("provider")
        if provider == "bbb" and not cleaned_data.get("bbb_configuration"):
            self.add_error(
                "bbb_configuration",
                "برای کلاس BigBlueButton انتخاب سرویس الزامی است.",
            )
        if provider == "skyroom" and not cleaned_data.get("skyroom_url"):
            self.add_error(
                "skyroom_url",
                "برای کلاس اسکای‌روم وارد کردن لینک الزامی است.",
            )
        return cleaned_data

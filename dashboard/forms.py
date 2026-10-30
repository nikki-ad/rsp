from django import forms
from core.jalali import JalaliDateField, JalaliDateTimeField
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.forms import inlineformset_factory
from django.utils import timezone

from academic.models import AcademicYear, Classroom, Enrollment, Grade
from accounts.models import StudentProfile, TeacherProfile
from notifications.models import Announcement
from online_classes.models import BBBConfiguration, OnlineClass
from reports.models import ReportCardPeriod, StudentReportCard
from accounts.choices import Role
from cafeteria.models import CafeteriaMenu, CafeteriaPaymentCard, CafeteriaWeek


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
    start_date = JalaliDateField(label="تاریخ شروع هفته")
    class Meta:
        model = CafeteriaWeek
        fields = ("title", "start_date", "is_active")

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


CafeteriaPaymentCardFormSet = inlineformset_factory(
    CafeteriaWeek,
    CafeteriaPaymentCard,
    fields=("card_number", "card_holder"),
    extra=2,
    can_delete=True,
    widgets={
        "card_number": forms.TextInput(
            attrs={
                "dir": "ltr",
                "inputmode": "numeric",
                "autocomplete": "off",
            }
        ),
    },
)


class AcademicYearForm(forms.ModelForm):
    start_date = JalaliDateField(required=False, label="تاریخ شروع")
    end_date = JalaliDateField(required=False, label="تاریخ پایان")
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
        queryset=TeacherProfile.objects.select_related("user").filter(is_language_teacher=False),
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
            .filter(user__is_active=True, is_language_teacher=False)
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
    publish_at = JalaliDateTimeField(label="زمان انتشار (شمسی)", initial=timezone.now)

    class Meta:
        model = Announcement
        fields = ("title", "message", "image", "audience", "classrooms", "teachers", "publish_at", "is_active")
        widgets = {
            "image": forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp,image/gif"}),
            "message": forms.Textarea(attrs={"rows": 5}),
            "classrooms": forms.CheckboxSelectMultiple,
            "teachers": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["audience"].choices = [
            (value, label) for value, label in Announcement.Audience.choices
            if value != Announcement.Audience.CLASSROOM
        ]
        self.fields["classrooms"].queryset = Classroom.objects.filter(
            academic_year__status=AcademicYear.Status.ACTIVE
        ).select_related("grade", "academic_year").order_by("grade__order", "name")
        self.fields["teachers"].queryset = TeacherProfile.objects.filter(
            user__is_active=True
        ).select_related("user").order_by("user__last_name", "user__first_name")
        self.fields["classrooms"].help_text = "اطلاعیه فقط برای دانش‌آموزان کلاس‌های تیک‌خورده ارسال می‌شود."
        self.fields["teachers"].help_text = "اطلاعیه فقط برای معلمان تیک‌خورده ارسال می‌شود."
        if not self.is_bound and self.instance.audience == Announcement.Audience.CLASSROOM:
            self.initial["audience"] = Announcement.Audience.STUDENTS
            self.initial["classrooms"] = [self.instance.classroom_id]

    def clean(self):
        data = super().clean()
        audience = data.get("audience")
        for name, relevant in (("classrooms", Announcement.Audience.STUDENTS), ("teachers", Announcement.Audience.TEACHERS)):
            if audience == relevant:
                if not data.get(name):
                    self.add_error(name, "حداقل یک گیرنده انتخاب کنید.")
            else:
                data[name] = self.fields[name].queryset.none()
        self.instance.classroom = None
        self.instance.targeted = audience in {Announcement.Audience.STUDENTS, Announcement.Audience.TEACHERS}
        return data


class ReportCardPeriodForm(forms.ModelForm):
    class Meta:
        model = ReportCardPeriod
        fields = ("title", "academic_year")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["academic_year"].required = True


class ReportCardForm(forms.ModelForm):
    student_search = forms.CharField(
        label="جست‌وجوی دانش‌آموز", required=False,
        widget=forms.TextInput(attrs={"autocomplete": "off", "placeholder": "نام یا نام خانوادگی را بنویسید و از نتایج انتخاب کنید"}),
    )

    class Meta:
        model = StudentReportCard
        fields = ("period", "student_search", "student", "file", "is_active")
        widgets = {
            "student": forms.HiddenInput,
            "file": forms.ClearableFileInput(attrs={"accept": ".pdf,.jpg,.jpeg,.png,.webp"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        students = StudentProfile.objects.select_related("user").prefetch_related(
            "enrollments__classroom__grade", "enrollments__academic_year",
        ).order_by("user__last_name", "user__first_name")
        self.student_choices = []
        for student in students:
            classes = "، ".join(str(e.classroom) + " (" + str(e.academic_year) + ")" for e in student.enrollments.all() if e.is_active)
            label = f"{student} — {classes or 'بدون کلاس'} — {student.user.username}"
            self.student_choices.append({"id": str(student.pk), "label": label})
        selected = str(self["student"].value() or "")
        self.initial["student_search"] = next((s["label"] for s in self.student_choices if s["id"] == selected), "")
        self.fields["student"].error_messages["required"] = "دانش‌آموز را از نتایج جست‌وجو انتخاب کنید."

    def clean(self):
        data = super().clean()
        period, student = data.get("period"), data.get("student")
        if period and student:
            changing_target = (
                self.instance._state.adding
                or self.instance.period_id != period.pk
                or self.instance.student_id != student.pk
            )
            if changing_target and StudentReportCard.objects.filter(period=period, student=student).exclude(pk=self.instance.pk).exists():
                self.add_error("student_search", "برای این دانش‌آموز در این عنوان، کارنامه ثبت شده است؛ فایل قبلی را ویرایش کنید.")
            self.instance.title = period.title
        return data


class BBBConfigurationForm(forms.ModelForm):
    class Meta:
        model = BBBConfiguration
        fields = ("name", "api_url", "secret", "is_active")
        widgets = {
            "secret": forms.PasswordInput(render_value=True),
        }


class OnlineClassForm(forms.ModelForm):
    is_online_class = True

    class Meta:
        model = OnlineClass
        fields = (
            "title",
            "academic_year",
            "provider",
            "bbb_configuration",
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
        self.fields["bbb_configuration"].queryset = BBBConfiguration.objects.filter(is_active=True)
        self.fields["bbb_configuration"].help_text = "شناسه اتاق خودکار ساخته می‌شود؛ نیازی به واردکردن شناسه در پنل BBB نیست."
        year_id = self.data.get("academic_year") if self.is_bound else self.instance.academic_year_id
        if not self.is_bound and not year_id:
            year_id = AcademicYear.objects.filter(status=AcademicYear.Status.ACTIVE).values_list("id", flat=True).first()
            self.initial["academic_year"] = year_id
        from uuid import UUID
        try:
            year_id = UUID(str(year_id)) if year_id else None
        except ValueError:
            year_id = None
        student_qs = StudentProfile.objects.select_related("user").filter(
            enrollments__academic_year_id=year_id, enrollments__is_active=True,
        ).distinct() if year_id else StudentProfile.objects.none()
        teacher_qs = TeacherProfile.objects.select_related("user")
        self.fields["students"].queryset = student_qs.order_by(
            "user__last_name",
            "user__first_name",
        )
        self.fields["teachers"].queryset = teacher_qs.order_by(
            "user__last_name",
            "user__first_name",
        )

        self.student_classroom_data = online_class_people(year_id)

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


def online_class_people(year_id):
    """Only active enrollments in the selected year; IDs are student profile IDs."""
    classrooms = Classroom.objects.filter(academic_year_id=year_id).select_related("grade") if year_id else Classroom.objects.none()
    enrollments = Enrollment.objects.filter(
        academic_year_id=year_id, is_active=True,
    ).select_related("student__user").order_by("student__user__last_name", "student__user__first_name") if year_id else Enrollment.objects.none()
    groups = {str(room.id): {"id": str(room.id), "name": str(room), "students": []} for room in classrooms}
    for enrollment in enrollments:
        group = groups.get(str(enrollment.classroom_id))
        if group is not None:
            group["students"].append({"id": str(enrollment.student_id), "name": str(enrollment.student)})
    return list(groups.values())


class LanguageOnlineClassForm(OnlineClassForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from language_unit.models import LanguageGroup
        from uuid import UUID
        year = self.data.get("academic_year") if self.is_bound else self.initial.get("academic_year", self.instance.academic_year_id)
        try:
            year = UUID(str(year))
        except (ValueError, TypeError):
            year = None
        groups = LanguageGroup.objects.filter(academic_year_id=year, is_active=True)
        self.fields["students"].queryset = StudentProfile.objects.filter(language_groups__in=groups).select_related("user").distinct()
        self.fields["teachers"].queryset = TeacherProfile.objects.filter(is_language_teacher=True).select_related("user")
        self.student_classroom_data = language_online_people(year)


def language_online_people(year):
    from language_unit.models import LanguageGroup
    groups = LanguageGroup.objects.filter(academic_year_id=year, is_active=True).prefetch_related("students__user")
    return [{"id": str(group.pk), "name": str(group), "students": [
        {"id": str(student.pk), "name": str(student)} for student in group.students.all()
    ]} for group in groups]

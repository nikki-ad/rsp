from django.db import models
from core.models import BaseModel


class EducationalMaterial(BaseModel):

    TYPE_CHOICES = (
        ("text", "متن"),
        ("file", "فایل"), ("image", "عکس"), ("video", "فیلم"),
        ("link", "لینک"),
    )

    teacher = models.ForeignKey(
        "accounts.TeacherProfile",
        on_delete=models.CASCADE,
        related_name="materials",
        verbose_name="معلم",
    )

    title = models.CharField(
        max_length=200,
        verbose_name="عنوان",
    )

    content_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default="text",
        verbose_name="نوع محتوا",
    )

    content = models.TextField(
        blank=True,
        null=True,
        verbose_name="متن مطلب",
    )

    file = models.FileField(
        upload_to="educational_materials/",
        blank=True,
        null=True,
        verbose_name="فایل",
    )

    link = models.URLField(
        blank=True,
        null=True,
        verbose_name="لینک",
    )

    classrooms = models.ManyToManyField(
        "academic.Classroom",
        related_name="materials",
        verbose_name="کلاس‌ها",
    )


    def clean(self):
        super().clean()
        if self.content_type == "video" and self.file:
            from core.uploads import validate_video
            from django.core.exceptions import ValidationError
            try:
                validate_video(self.file)
            except ValidationError as error:
                raise ValidationError({"file": error})

    class Meta:
        verbose_name = "مطلب آموزشی"
        verbose_name_plural = "مطالب آموزشی"


    def __str__(self):
        return self.title
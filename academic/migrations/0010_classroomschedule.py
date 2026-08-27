from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("academic", "0009_academicyear_unique_active_academic_year"),
    ]

    operations = [
        migrations.CreateModel(
            name="ClassroomSchedule",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "day",
                    models.CharField(
                        choices=[
                            ("saturday", "شنبه"),
                            ("sunday", "یکشنبه"),
                            ("monday", "دوشنبه"),
                            ("tuesday", "سه‌شنبه"),
                            ("wednesday", "چهارشنبه"),
                        ],
                        max_length=20,
                        verbose_name="روز",
                    ),
                ),
                (
                    "period",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "زنگ اول"),
                            (2, "زنگ دوم"),
                            (3, "زنگ سوم"),
                            (4, "زنگ چهارم"),
                            (5, "زنگ پنجم"),
                        ],
                        verbose_name="زنگ",
                    ),
                ),
                (
                    "subject",
                    models.CharField(
                        blank=True,
                        max_length=100,
                        verbose_name="درس / فعالیت",
                    ),
                ),
                (
                    "classroom",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="weekly_schedule",
                        to="academic.classroom",
                        verbose_name="کلاس",
                    ),
                ),
            ],
            options={
                "verbose_name": "برنامه هفتگی کلاس",
                "verbose_name_plural": "برنامه‌های هفتگی کلاس‌ها",
                "ordering": ["classroom", "day", "period"],
            },
        ),
        migrations.AddConstraint(
            model_name="classroomschedule",
            constraint=models.UniqueConstraint(
                fields=("classroom", "day", "period"),
                name="unique_classroom_schedule_slot",
            ),
        ),
    ]

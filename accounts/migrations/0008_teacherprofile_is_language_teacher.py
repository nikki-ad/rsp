from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0007_alter_studentprofile_guardian_name_and_more")]
    operations = [migrations.AddField(
        model_name="teacherprofile", name="is_language_teacher",
        field=models.BooleanField(default=False, verbose_name="معلم واحد زبان",
            help_text="این معلم فقط به گروه‌های زبان دسترسی دارد و به کلاس‌های مدرسه دسترسی ندارد."),
    )]

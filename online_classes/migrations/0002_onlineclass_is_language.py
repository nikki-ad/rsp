from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("online_classes", "0001_initial")]
    operations = [migrations.AddField(
        model_name="onlineclass", name="is_language",
        field=models.BooleanField(default=False, verbose_name="کلاس واحد زبان"),
    )]

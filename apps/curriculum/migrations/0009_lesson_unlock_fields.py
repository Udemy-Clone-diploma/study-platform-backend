from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("curriculum", "0008_merge_20260617_1228"),
    ]

    operations = [
        migrations.AddField(
            model_name="Lesson",
            name="unlock_after_days",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="Lesson",
            name="requires_previous",
            field=models.BooleanField(default=False),
        ),
    ]

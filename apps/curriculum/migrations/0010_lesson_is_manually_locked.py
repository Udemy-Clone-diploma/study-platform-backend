from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("curriculum", "0009_lesson_unlock_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="Lesson",
            name="is_manually_locked",
            field=models.BooleanField(default=False),
        ),
    ]

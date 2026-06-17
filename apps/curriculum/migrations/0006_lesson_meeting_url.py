from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("curriculum", "0005_lesson_original_video_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="lesson",
            name="meeting_url",
            field=models.URLField(blank=True, null=True),
        ),
    ]

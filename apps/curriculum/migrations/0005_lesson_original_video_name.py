from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("curriculum", "0004_lesson_document"),
    ]

    operations = [
        migrations.AddField(
            model_name="lesson",
            name="original_video_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
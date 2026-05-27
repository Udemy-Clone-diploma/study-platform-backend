import apps.common.files
from django.db import migrations, models


class Migration(migrations.Migration):
    """Register content/min_score/video fields on curriculum.Lesson at state level only.

    These columns were physically added by courses/0014_lesson_fields when Lesson
    still lived in courses. The DB table already has them; this migration just brings
    Django's curriculum app state into sync with the actual model definition.
    """

    dependencies = [
        ("curriculum", "0002_add_test_question"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="lesson",
                    name="content",
                    field=models.TextField(blank=True, default=""),
                ),
                migrations.AddField(
                    model_name="lesson",
                    name="min_score",
                    field=models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="lesson",
                    name="video",
                    field=models.FileField(
                        blank=True,
                        null=True,
                        upload_to=apps.common.files.UUIDUploadTo("lessons/videos"),
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]

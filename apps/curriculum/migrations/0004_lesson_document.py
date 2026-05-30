import apps.common.files
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("curriculum", "0003_lesson_content_lesson_min_score_lesson_video"),
    ]

    operations = [
        migrations.CreateModel(
            name="LessonDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.FileField(upload_to=apps.common.files.UUIDUploadTo("lessons/documents"))),
                ("original_name", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("lesson", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="documents",
                    to="curriculum.lesson",
                )),
            ],
            options={"db_table": "lesson_documents", "ordering": ["created_at"]},
        ),
    ]

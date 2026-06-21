import apps.common.files
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("curriculum", "0005_lesson_original_video_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="LessonItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "item_type",
                    models.CharField(
                        choices=[("text", "Text"), ("video", "Video"), ("test", "Test")],
                        max_length=10,
                    ),
                ),
                ("order", models.PositiveSmallIntegerField()),
                ("content", models.TextField(blank=True, default="")),
                ("body_html", models.TextField(blank=True, null=True)),
                (
                    "video",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to=apps.common.files.UUIDUploadTo("lesson_items/videos"),
                    ),
                ),
                ("video_url", models.URLField(blank=True, null=True)),
                ("original_video_name", models.CharField(blank=True, default="", max_length=255)),
                ("duration_minutes", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "lesson",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="curriculum.lesson",
                    ),
                ),
                (
                    "test",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="lesson_items",
                        to="curriculum.test",
                    ),
                ),
            ],
            options={
                "db_table": "lesson_items",
                "ordering": ["order"],
            },
        ),
        migrations.AddConstraint(
            model_name="lessonitem",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_deleted=False),
                fields=["lesson", "order"],
                name="unique_active_lesson_item_order",
            ),
        ),
    ]

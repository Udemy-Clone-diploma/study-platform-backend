import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Register Module and Lesson with the curriculum app at state level only.

    Models moved over from courses (see courses/0016); db tables `modules` and
    `lessons` already exist, so this migration touches only Django state.
    """

    initial = True

    dependencies = [
        ("courses", "0016_move_module_lesson_to_curriculum"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="Module",
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
                        ("title", models.CharField(max_length=255)),
                        ("description", models.TextField(blank=True)),
                        ("order", models.PositiveSmallIntegerField()),
                        ("is_deleted", models.BooleanField(default=False)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "course",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="modules",
                                to="courses.course",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "modules",
                        "ordering": ["order"],
                    },
                ),
                migrations.CreateModel(
                    name="Lesson",
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
                        ("title", models.CharField(max_length=255)),
                        ("order", models.PositiveSmallIntegerField()),
                        (
                            "duration_minutes",
                            models.PositiveSmallIntegerField(blank=True, null=True),
                        ),
                        ("is_preview", models.BooleanField(default=False)),
                        (
                            "content_type",
                            models.CharField(
                                choices=[("video", "Video"), ("text", "Text")],
                                default="video",
                                max_length=10,
                            ),
                        ),
                        ("video_url", models.URLField(blank=True, null=True)),
                        ("body_html", models.TextField(blank=True, null=True)),
                        ("is_deleted", models.BooleanField(default=False)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "module",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="lessons",
                                to="curriculum.module",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "lessons",
                        "ordering": ["order"],
                    },
                ),
                migrations.AddConstraint(
                    model_name="module",
                    constraint=models.UniqueConstraint(
                        fields=("course", "order"),
                        condition=models.Q(("is_deleted", False)),
                        name="unique_active_module_order_per_course",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="lesson",
                    constraint=models.UniqueConstraint(
                        fields=("module", "order"),
                        condition=models.Q(("is_deleted", False)),
                        name="unique_active_lesson_order_per_module",
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]

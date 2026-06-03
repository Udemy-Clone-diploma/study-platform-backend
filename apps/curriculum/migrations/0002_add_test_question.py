import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Register Test and Question with the curriculum app at state level only.

    Models moved over from courses (see courses/0018); db tables `tests` and
    `questions` already exist, so this migration touches only Django state.
    """

    dependencies = [
        ("curriculum", "0001_initial"),
        ("courses", "0018_move_test_question_to_curriculum"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="Test",
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
                        ("description", models.TextField(blank=True, default="")),
                        ("passing_score", models.PositiveSmallIntegerField(default=70)),
                        ("order", models.PositiveSmallIntegerField()),
                        ("is_deleted", models.BooleanField(default=False)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "module",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="tests",
                                to="curriculum.module",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "tests",
                        "ordering": ["order"],
                    },
                ),
                migrations.CreateModel(
                    name="Question",
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
                        (
                            "question_type",
                            models.CharField(
                                choices=[
                                    ("multiple_choice", "Multiple Choice"),
                                    ("true_false", "True/False"),
                                    ("short_answer", "Short Answer"),
                                ],
                                default="multiple_choice",
                                max_length=20,
                            ),
                        ),
                        ("text", models.TextField()),
                        ("options", models.JSONField(blank=True, default=list)),
                        ("correct_index", models.SmallIntegerField(blank=True, null=True)),
                        ("correct_bool", models.BooleanField(blank=True, null=True)),
                        ("sample_answer", models.TextField(blank=True, default="")),
                        ("order", models.PositiveSmallIntegerField()),
                        ("is_deleted", models.BooleanField(default=False)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "test",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="questions",
                                to="curriculum.test",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "questions",
                        "ordering": ["order"],
                    },
                ),
                migrations.AddConstraint(
                    model_name="test",
                    constraint=models.UniqueConstraint(
                        fields=("module", "order"),
                        condition=models.Q(is_deleted=False),
                        name="unique_active_test_order_per_module",
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]

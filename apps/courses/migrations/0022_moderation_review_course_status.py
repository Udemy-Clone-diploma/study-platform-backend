from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0021_course_moderator_comment"),
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ModerationReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("basics_comment", models.TextField(blank=True, default="")),
                ("basics_action", models.CharField(blank=True, default="", max_length=20)),
                ("basics_field_statuses", models.JSONField(blank=True, default=dict)),
                ("content_comment", models.TextField(blank=True, default="")),
                ("content_action", models.CharField(blank=True, default="", max_length=20)),
                ("content_item_statuses", models.JSONField(blank=True, default=dict)),
                ("final_action", models.CharField(blank=True, default="", max_length=20)),
                ("final_comment", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "course",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="moderation_review",
                        to="courses.course",
                    ),
                ),
                (
                    "moderator_profile",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="moderation_reviews",
                        to="users.moderatorprofile",
                    ),
                ),
            ],
            options={"db_table": "course_moderation_reviews"},
        ),
        migrations.AlterField(
            model_name="course",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("review", "Review"),
                    ("needs_revision", "Needs Revision (returned by moderator)"),
                    ("rejected", "Rejected"),
                    ("published", "Published"),
                    ("hidden", "Hidden (active but not listed)"),
                    ("archived", "Archived"),
                ],
                default="draft",
                max_length=20,
            ),
        ),
    ]

import apps.common.files
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0019_add_hidden_course_status"),
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CoursePendingEdit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(
                    choices=[
                        ("draft", "Draft"),
                        ("pending", "Pending Moderation"),
                        ("needs_revision", "Needs Revision"),
                    ],
                    default="draft",
                    max_length=20,
                )),
                ("title", models.CharField(max_length=255)),
                ("subtitle", models.CharField(blank=True, max_length=255, null=True)),
                ("short_description", models.CharField(max_length=500)),
                ("full_description", models.TextField()),
                ("image", models.ImageField(blank=True, null=True, upload_to=apps.common.files.UUIDUploadTo("courses/pending"))),
                ("level", models.CharField(max_length=20)),
                ("language", models.CharField(max_length=20)),
                ("mode", models.CharField(max_length=20)),
                ("delivery_type", models.CharField(max_length=20)),
                ("course_type", models.CharField(max_length=30)),
                ("duration_hours", models.PositiveIntegerField()),
                ("with_certificate", models.BooleanField(default=False)),
                ("is_on_sale", models.BooleanField(default=False)),
                ("tag_ids", models.JSONField(default=list)),
                ("modules_snapshot", models.JSONField(default=list)),
                ("moderator_comment", models.TextField(blank=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("category", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to="courses.category",
                )),
                ("course", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="pending_edit",
                    to="courses.course",
                )),
                ("moderator_profile", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to="users.moderatorprofile",
                )),
            ],
            options={"db_table": "course_pending_edits"},
        ),
    ]
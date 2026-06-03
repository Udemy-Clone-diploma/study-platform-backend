import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0019_add_hidden_course_status"),
        ("enrollments", "0003_enrollment_is_completed"),
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="enrollment",
            name="is_completed",
        ),
        migrations.CreateModel(
            name="CourseCompletion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("teacher_name", models.CharField(max_length=255)),
                ("level", models.CharField(max_length=20)),
                ("image_url", models.TextField(blank=True, null=True)),
                ("progress_percent", models.PositiveSmallIntegerField(default=0)),
                ("started_at", models.DateTimeField()),
                ("completed_at", models.DateTimeField(auto_now_add=True)),
                ("final_score", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("certificate_url", models.TextField(blank=True, null=True)),
                (
                    "course",
                    models.ForeignKey(
                        blank=True,
                        db_column="id_course",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="completions",
                        to="courses.course",
                    ),
                ),
                (
                    "student_profile",
                    models.ForeignKey(
                        db_column="id_student_profile",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="course_completions",
                        to="users.studentprofile",
                    ),
                ),
            ],
            options={
                "db_table": "course_completions",
                "ordering": ["-completed_at"],
            },
        ),
    ]

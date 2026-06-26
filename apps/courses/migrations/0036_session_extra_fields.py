import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0035_session_personal_event"),
        ("users", "0012_merge_20260515_2029"),
    ]

    operations = [
        # Remove old constraint (slot XOR schedule)
        migrations.RemoveConstraint(model_name="session", name="session_exactly_one_source"),

        # Add fields for extra sessions
        migrations.AddField(
            model_name="session",
            name="course",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+", to="courses.course",
            ),
        ),
        migrations.AddField(
            model_name="session",
            name="cohort",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+", to="courses.cohort",
            ),
        ),
        migrations.AddField(
            model_name="session",
            name="student_profile",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+", to="users.studentprofile",
            ),
        ),

        migrations.AddIndex(
            model_name="session",
            index=models.Index(fields=["course", "date"], name="sessions_course_date_idx"),
        ),

        # New constraint: slot XOR schedule XOR course
        migrations.AddConstraint(
            model_name="session",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(slot__isnull=False, schedule__isnull=True,  course__isnull=True)
                    | models.Q(slot__isnull=True,  schedule__isnull=False, course__isnull=True)
                    | models.Q(slot__isnull=True,  schedule__isnull=True,  course__isnull=False)
                ),
                name="session_source_valid",
            ),
        ),
    ]

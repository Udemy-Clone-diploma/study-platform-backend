from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0028_cohort_enrollment_open"),
        ("enrollments", "0005_enrollment_last_lesson_enrollment_last_opened_at_and_more"),
        ("users", "0012_merge_20260515_2029"),
    ]

    operations = [
        # ScheduleSlot — individual delivery format time slots
        migrations.CreateModel(
            name="ScheduleSlot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "delivery_format",
                    models.ForeignKey(
                        limit_choices_to={"format_type": "individual"},
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="schedule_slots",
                        to="courses.coursedeliveryformat",
                    ),
                ),
                (
                    "day_of_week",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (0, "Monday"), (1, "Tuesday"), (2, "Wednesday"),
                            (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday"),
                        ]
                    ),
                ),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                (
                    "booked_by",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="scheduled_slot",
                        to="enrollments.enrollment",
                    ),
                ),
                (
                    "original_day_of_week",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        null=True,
                        choices=[
                            (0, "Monday"), (1, "Tuesday"), (2, "Wednesday"),
                            (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday"),
                        ],
                    ),
                ),
                ("original_start_time", models.TimeField(blank=True, null=True)),
                ("original_end_time", models.TimeField(blank=True, null=True)),
                ("is_rescheduled", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "schedule_slots", "ordering": ["day_of_week", "start_time"]},
        ),

        # CohortSchedule — fixed weekly group session
        migrations.CreateModel(
            name="CohortSchedule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "cohort",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="schedules",
                        to="courses.cohort",
                    ),
                ),
                (
                    "day_of_week",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (0, "Monday"), (1, "Tuesday"), (2, "Wednesday"),
                            (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday"),
                        ]
                    ),
                ),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "cohort_schedules", "ordering": ["day_of_week", "start_time"]},
        ),
        migrations.AddConstraint(
            model_name="cohortschedule",
            constraint=models.UniqueConstraint(
                fields=["cohort", "day_of_week", "start_time"],
                name="unique_cohort_schedule_slot",
            ),
        ),

        # TeacherUnavailability — personal blocks
        migrations.CreateModel(
            name="TeacherUnavailability",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "teacher_profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="unavailabilities",
                        to="users.teacherprofile",
                    ),
                ),
                (
                    "recurrence_type",
                    models.CharField(
                        choices=[("weekly", "Every week"), ("one_time", "One-time block")],
                        default="weekly",
                        max_length=10,
                    ),
                ),
                (
                    "day_of_week",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (0, "Monday"), (1, "Tuesday"), (2, "Wednesday"),
                            (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday"),
                        ]
                    ),
                ),
                ("date", models.DateField(blank=True, null=True)),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("reason", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "teacher_unavailabilities", "ordering": ["day_of_week", "start_time"]},
        ),
    ]

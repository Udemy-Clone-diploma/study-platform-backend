"""
State-only migration: registers the 7 schedule-domain models with the
apps.schedule app.  All DB tables already exist (created by the courses app
migrations); only Django's migration state changes here.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("courses", "0038_rename_sessions_schedule_date_idx_sessions_schedul_8b7510_idx_and_more"),
        ("curriculum", "0010_lesson_is_manually_locked"),
        ("enrollments", "0006_add_delivery_format_to_enrollment"),
        ("users", "0012_merge_20260515_2029"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[

                # ── 1. CohortSchedule ──────────────────────────────────────────
                migrations.CreateModel(
                    name="CohortSchedule",
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
                        (
                            "cohort",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="schedules",
                                to="courses.cohort",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "cohort_schedules",
                        "ordering": ["day_of_week", "start_time"],
                    },
                ),
                migrations.AddConstraint(
                    model_name="cohortschedule",
                    constraint=models.UniqueConstraint(
                        fields=["cohort", "day_of_week", "start_time"],
                        name="unique_cohort_schedule_slot",
                    ),
                ),

                # ── 2. ScheduleSlot ────────────────────────────────────────────
                migrations.CreateModel(
                    name="ScheduleSlot",
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
                            "original_day_of_week",
                            models.PositiveSmallIntegerField(
                                blank=True,
                                choices=[
                                    (0, "Monday"), (1, "Tuesday"), (2, "Wednesday"),
                                    (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday"),
                                ],
                                null=True,
                            ),
                        ),
                        ("original_start_time", models.TimeField(blank=True, null=True)),
                        ("original_end_time", models.TimeField(blank=True, null=True)),
                        ("is_rescheduled", models.BooleanField(default=False)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "delivery_format",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="schedule_slots",
                                to="courses.coursedeliveryformat",
                            ),
                        ),
                        (
                            "booked_by",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="scheduled_slots",
                                to="enrollments.enrollment",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "schedule_slots",
                        "ordering": ["day_of_week", "start_time"],
                    },
                ),

                # ── 3. TeacherUnavailability ───────────────────────────────────
                migrations.CreateModel(
                    name="TeacherUnavailability",
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
                            "recurrence_type",
                            models.CharField(
                                choices=[
                                    ("weekly", "Every week"),
                                    ("one_time", "One-time block"),
                                    ("date_range", "Date range"),
                                ],
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
                        ("date_to", models.DateField(blank=True, null=True)),
                        ("start_time", models.TimeField()),
                        ("end_time", models.TimeField()),
                        ("reason", models.CharField(blank=True, default="", max_length=255)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        (
                            "teacher_profile",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="unavailabilities",
                                to="users.teacherprofile",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "teacher_unavailabilities",
                        "ordering": ["day_of_week", "start_time"],
                    },
                ),

                # ── 4. PersonalEvent ───────────────────────────────────────────
                migrations.CreateModel(
                    name="PersonalEvent",
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
                        ("date", models.DateField()),
                        ("start_time", models.TimeField()),
                        ("end_time", models.TimeField()),
                        ("meeting_link", models.URLField(blank=True, null=True)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "owner",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="personal_events",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        "db_table": "personal_events",
                        "ordering": ["date", "start_time"],
                    },
                ),

                # ── 5. Session ─────────────────────────────────────────────────
                migrations.CreateModel(
                    name="Session",
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
                        ("date", models.DateField()),
                        ("start_time", models.TimeField()),
                        ("end_time", models.TimeField()),
                        ("meeting_link", models.URLField(blank=True, null=True)),
                        (
                            "status",
                            models.CharField(
                                choices=[
                                    ("scheduled", "Scheduled"),
                                    ("cancelled", "Cancelled"),
                                    ("rescheduled", "Rescheduled"),
                                ],
                                default="scheduled",
                                max_length=20,
                            ),
                        ),
                        ("rescheduled_to_date", models.DateField(blank=True, null=True)),
                        ("rescheduled_from_date", models.DateField(blank=True, null=True)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "slot",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="sessions",
                                to="schedule.scheduleslot",
                            ),
                        ),
                        (
                            "schedule",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="sessions",
                                to="schedule.cohortschedule",
                            ),
                        ),
                        (
                            "course",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="+",
                                to="courses.course",
                            ),
                        ),
                        (
                            "cohort",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="+",
                                to="courses.cohort",
                            ),
                        ),
                        (
                            "student_profile",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="+",
                                to="users.studentprofile",
                            ),
                        ),
                        (
                            "lesson",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="+",
                                to="curriculum.lesson",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "sessions",
                    },
                ),
                migrations.AddConstraint(
                    model_name="session",
                    constraint=models.CheckConstraint(
                        condition=(
                            models.Q(slot__isnull=False, schedule__isnull=True, course__isnull=True)
                            | models.Q(slot__isnull=True, schedule__isnull=False, course__isnull=True)
                            | models.Q(slot__isnull=True, schedule__isnull=True, course__isnull=False)
                        ),
                        name="session_source_valid",
                    ),
                ),
                migrations.AddIndex(
                    model_name="session",
                    index=models.Index(
                        fields=["schedule", "date"],
                        name="sessions_schedul_8b7510_idx",
                    ),
                ),
                migrations.AddIndex(
                    model_name="session",
                    index=models.Index(
                        fields=["slot", "date"],
                        name="sessions_slot_id_9c66f7_idx",
                    ),
                ),
                migrations.AddIndex(
                    model_name="session",
                    index=models.Index(
                        fields=["course", "date"],
                        name="sessions_course__cc4c6e_idx",
                    ),
                ),

                # ── 6. ScheduleOverride ────────────────────────────────────────
                migrations.CreateModel(
                    name="ScheduleOverride",
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
                        ("original_date", models.DateField()),
                        (
                            "status",
                            models.CharField(
                                choices=[
                                    ("cancelled", "Cancelled"),
                                    ("rescheduled", "Rescheduled"),
                                ],
                                max_length=20,
                            ),
                        ),
                        ("new_date", models.DateField(blank=True, null=True)),
                        ("new_start_time", models.TimeField(blank=True, null=True)),
                        ("new_end_time", models.TimeField(blank=True, null=True)),
                        ("meeting_link", models.URLField(blank=True, null=True)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        (
                            "slot",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="overrides",
                                to="schedule.scheduleslot",
                            ),
                        ),
                        (
                            "schedule",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="overrides",
                                to="schedule.cohortschedule",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "schedule_overrides",
                    },
                ),
                migrations.AddConstraint(
                    model_name="scheduleoverride",
                    constraint=models.CheckConstraint(
                        condition=(
                            models.Q(slot__isnull=False, schedule__isnull=True)
                            | models.Q(slot__isnull=True, schedule__isnull=False)
                        ),
                        name="schedule_override_exactly_one_source",
                    ),
                ),

                # ── 7. EventInvitation ─────────────────────────────────────────
                migrations.CreateModel(
                    name="EventInvitation",
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
                            "status",
                            models.CharField(
                                choices=[
                                    ("pending", "Pending"),
                                    ("accepted", "Accepted"),
                                    ("declined", "Declined"),
                                ],
                                default="pending",
                                max_length=20,
                            ),
                        ),
                        ("responded_at", models.DateTimeField(blank=True, null=True)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        (
                            "event",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="invitations",
                                to="schedule.personalevent",
                            ),
                        ),
                        (
                            "invitee",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="event_invitations",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        "db_table": "event_invitations",
                    },
                ),
                migrations.AddConstraint(
                    model_name="eventinvitation",
                    constraint=models.UniqueConstraint(
                        fields=["event", "invitee"],
                        name="unique_event_invitation",
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]
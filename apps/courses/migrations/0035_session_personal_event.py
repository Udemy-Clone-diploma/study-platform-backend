import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0034_add_lesson_to_slots"),
        ("curriculum", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── Remove lesson + meeting_link from CohortSchedule ──────────────────
        migrations.RemoveField(model_name="cohortschedule", name="lesson"),
        migrations.RemoveField(model_name="cohortschedule", name="meeting_link"),

        # ── Remove lesson + meeting_link from ScheduleSlot ────────────────────
        migrations.RemoveField(model_name="scheduleslot", name="lesson"),
        migrations.RemoveField(model_name="scheduleslot", name="meeting_link"),

        # ── Session ───────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="Session",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("meeting_link", models.URLField(blank=True, null=True)),
                ("status", models.CharField(choices=[("scheduled", "Scheduled"), ("cancelled", "Cancelled"), ("rescheduled", "Rescheduled")], default="scheduled", max_length=20)),
                ("rescheduled_to_date", models.DateField(blank=True, null=True)),
                ("rescheduled_from_date", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("lesson", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="curriculum.lesson")),
                ("schedule", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="sessions", to="courses.cohortschedule")),
                ("slot", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="sessions", to="courses.scheduleslot")),
            ],
            options={"db_table": "sessions"},
        ),
        migrations.AddIndex(
            model_name="session",
            index=models.Index(fields=["schedule", "date"], name="sessions_schedule_date_idx"),
        ),
        migrations.AddIndex(
            model_name="session",
            index=models.Index(fields=["slot", "date"], name="sessions_slot_date_idx"),
        ),
        migrations.AddConstraint(
            model_name="session",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(slot__isnull=False, schedule__isnull=True)
                    | models.Q(slot__isnull=True, schedule__isnull=False)
                ),
                name="session_exactly_one_source",
            ),
        ),

        # ── PersonalEvent ─────────────────────────────────────────────────────
        migrations.CreateModel(
            name="PersonalEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("date", models.DateField()),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("meeting_link", models.URLField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="personal_events", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "personal_events", "ordering": ["date", "start_time"]},
        ),

        # ── EventInvitation ───────────────────────────────────────────────────
        migrations.CreateModel(
            name="EventInvitation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "Pending"), ("accepted", "Accepted"), ("declined", "Declined")], default="pending", max_length=20)),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="invitations", to="courses.personalevent")),
                ("invitee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="event_invitations", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "event_invitations"},
        ),
        migrations.AddConstraint(
            model_name="eventinvitation",
            constraint=models.UniqueConstraint(fields=["event", "invitee"], name="unique_event_invitation"),
        ),
    ]

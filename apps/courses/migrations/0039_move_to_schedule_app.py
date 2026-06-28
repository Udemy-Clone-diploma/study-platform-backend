"""
State-only migration: removes the 7 schedule-domain models from the courses app
state.  DB tables are untouched (handled by schedule/0001_initial.py).
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0038_rename_sessions_schedule_date_idx_sessions_schedul_8b7510_idx_and_more"),
        ("schedule", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name="EventInvitation"),
                migrations.DeleteModel(name="PersonalEvent"),
                migrations.DeleteModel(name="ScheduleOverride"),
                migrations.DeleteModel(name="Session"),
                migrations.DeleteModel(name="TeacherUnavailability"),
                migrations.DeleteModel(name="ScheduleSlot"),
                migrations.DeleteModel(name="CohortSchedule"),
            ],
            database_operations=[],
        ),
    ]
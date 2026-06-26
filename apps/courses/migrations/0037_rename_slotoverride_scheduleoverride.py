from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0036_session_extra_fields'),
    ]

    operations = [
        # 1. Rename the Django model (updates app state + all FK references)
        migrations.RenameModel(
            old_name='SlotOverride',
            new_name='ScheduleOverride',
        ),
        # 2. Rename the physical DB table
        migrations.AlterModelTable(
            name='scheduleoverride',
            table='schedule_overrides',
        ),
        # 3. Rename the check constraint
        migrations.RemoveConstraint(
            model_name='scheduleoverride',
            name='slot_override_exactly_one_source',
        ),
        migrations.AddConstraint(
            model_name='scheduleoverride',
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(slot__isnull=False, schedule__isnull=True)
                    | models.Q(slot__isnull=True, schedule__isnull=False)
                ),
                name='schedule_override_exactly_one_source',
            ),
        ),
    ]

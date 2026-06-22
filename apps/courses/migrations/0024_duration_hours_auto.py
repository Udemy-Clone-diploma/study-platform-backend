from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0023_rejection_approval_records"),
    ]

    operations = [
        migrations.AlterField(
            model_name="course",
            name="duration_hours",
            field=models.PositiveIntegerField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name="coursependingedit",
            name="duration_hours",
            field=models.PositiveIntegerField(blank=True, default=0, null=True),
        ),
    ]

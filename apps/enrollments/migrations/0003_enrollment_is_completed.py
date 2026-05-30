from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("enrollments", "0002_enrollment_is_deleted"),
    ]

    operations = [
        migrations.AddField(
            model_name="enrollment",
            name="is_completed",
            field=models.BooleanField(default=False),
        ),
    ]

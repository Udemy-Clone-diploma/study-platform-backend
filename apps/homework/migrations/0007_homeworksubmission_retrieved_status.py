from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("homework", "0006_submission_best_test_attempt"),
    ]

    operations = [
        migrations.AlterField(
            model_name="homeworksubmission",
            name="status",
            field=models.CharField(
                choices=[
                    ("submitted", "Submitted"),
                    ("reviewed", "Reviewed"),
                    ("retrieved", "Retrieved"),
                ],
                default="submitted",
                max_length=20,
            ),
        ),
    ]

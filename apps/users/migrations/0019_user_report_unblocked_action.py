from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0018_merge_20260718_0105"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userreport",
            name="resolution",
            field=models.CharField(
                blank=True,
                choices=[
                    ("warning", "Warning"),
                    ("blocked", "Blocked"),
                    ("unblocked", "Unblocked"),
                    ("dismissed", "Dismissed"),
                ],
                default="",
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="userreportaction",
            name="action",
            field=models.CharField(
                choices=[
                    ("claimed", "Claimed"),
                    ("warning", "Warning"),
                    ("blocked", "Blocked"),
                    ("unblocked", "Unblocked"),
                    ("escalated", "Escalated"),
                    ("dismissed", "Dismissed"),
                ],
                max_length=16,
            ),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0031_scheduleslot_booked_by_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="scheduleslot",
            name="meeting_link",
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="cohortschedule",
            name="meeting_link",
            field=models.URLField(blank=True, null=True),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0002_add_homework_submitted_notification_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="type",
            field=models.CharField(
                choices=[
                    ("new_message", "New message"),
                    ("homework_submitted", "Homework submitted"),
                    ("homework_graded", "Homework graded"),
                    ("schedule_event", "Schedule event"),
                    ("new_lesson", "New lesson"),
                    ("moderation_action", "Moderation action"),
                ],
                max_length=32,
            ),
        ),
    ]

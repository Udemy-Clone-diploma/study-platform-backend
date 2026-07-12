from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0004_chat_moderation_actions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="chatmoderationaction",
            name="action",
            field=models.CharField(
                choices=[
                    ("warning", "Warning"),
                    ("retract_warning", "Warning retracted"),
                    ("restrict", "Chat access restricted"),
                    ("restore", "Chat access restored"),
                ],
                max_length=16,
            ),
        ),
    ]

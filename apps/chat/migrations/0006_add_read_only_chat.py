from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0005_add_retract_warning_action"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatroom",
            name="is_read_only",
            field=models.BooleanField(default=False),
        ),
    ]

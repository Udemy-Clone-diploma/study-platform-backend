import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0002_chat_history_clear_and_user_blocks"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MessageReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reason", models.CharField(choices=[("spam", "Spam or advertising"), ("harassment", "Harassment or bullying"), ("hate", "Hate speech"), ("violence", "Violence or threats"), ("sexual", "Sexual content"), ("fraud", "Fraud or scam"), ("other", "Other")], max_length=24)),
                ("details", models.CharField(blank=True, default="", max_length=500)),
                ("message_text", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("message", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reports", to="chat.message")),
                ("reporter", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reported_chat_messages", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "chat_message_reports", "ordering": ["-created_at", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="messagereport",
            constraint=models.UniqueConstraint(fields=("message", "reporter"), name="unique_message_reporter"),
        ),
        migrations.AddIndex(
            model_name="messagereport",
            index=models.Index(fields=["-created_at"], name="chat_report_created_idx"),
        ),
    ]

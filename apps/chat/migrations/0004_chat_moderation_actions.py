import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0003_message_reports"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ChatUserRestriction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reason", models.CharField(blank=True, default="", max_length=500)),
                ("is_active", models.BooleanField(default=True)),
                ("restricted_at", models.DateTimeField(auto_now_add=True)),
                ("lifted_at", models.DateTimeField(blank=True, null=True)),
                ("restricted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="chat_restrictions_created", to=settings.AUTH_USER_MODEL)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="chat_restriction", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "chat_user_restrictions"},
        ),
        migrations.CreateModel(
            name="ChatModerationAction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(choices=[("warning", "Warning"), ("restrict", "Chat access restricted"), ("restore", "Chat access restored")], max_length=16)),
                ("note", models.CharField(blank=True, default="", max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("moderator", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="chat_moderation_actions_created", to=settings.AUTH_USER_MODEL)),
                ("report", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="moderation_actions", to="chat.messagereport")),
                ("target_user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="chat_moderation_actions_received", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "chat_moderation_actions", "ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="chatuserrestriction",
            index=models.Index(fields=["is_active"], name="chat_restrict_active_idx"),
        ),
        migrations.AddIndex(
            model_name="chatmoderationaction",
            index=models.Index(fields=["target_user", "-created_at"], name="chat_mod_user_created_idx"),
        ),
    ]

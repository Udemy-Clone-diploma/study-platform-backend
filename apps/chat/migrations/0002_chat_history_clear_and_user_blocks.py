# Generated manually for chat participant history clearing and per-user chat blocks.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="chatparticipant",
            name="history_cleared_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="ChatUserBlock",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "blocked",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chat_blocks_received",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "blocker",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chat_blocks_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "chat_user_blocks",
            },
        ),
        migrations.AddIndex(
            model_name="chatuserblock",
            index=models.Index(fields=["blocker", "blocked"], name="chat_block_pair_idx"),
        ),
        migrations.AddIndex(
            model_name="chatuserblock",
            index=models.Index(fields=["blocked"], name="chat_block_blocked_idx"),
        ),
        migrations.AddConstraint(
            model_name="chatuserblock",
            constraint=models.UniqueConstraint(
                fields=("blocker", "blocked"),
                name="unique_chat_user_block",
            ),
        ),
        migrations.AddConstraint(
            model_name="chatuserblock",
            constraint=models.CheckConstraint(
                condition=~models.Q(blocker=models.F("blocked")),
                name="prevent_self_chat_user_block",
            ),
        ),
    ]

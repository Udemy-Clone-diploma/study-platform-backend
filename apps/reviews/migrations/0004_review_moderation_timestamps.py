from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reviews", "0003_review_is_deleted_review_moderation_status_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="review",
            name="moderation_assigned_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="review",
            name="moderated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

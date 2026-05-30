from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0020_course_pending_edit"),
    ]

    operations = [
        migrations.AddField(
            model_name="course",
            name="moderator_comment",
            field=models.TextField(blank=True, default=""),
        ),
    ]
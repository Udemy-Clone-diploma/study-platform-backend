from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0047_course_title_created_at_db_index"),
        ("chat", "0006_add_read_only_chat"),
    ]

    operations = [
        migrations.AddField(
            model_name="cohort",
            name="group_chat",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="cohort_group",
                to="chat.chatroom",
            ),
        ),
        migrations.AddField(
            model_name="coursedeliveryformat",
            name="group_chat",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="delivery_format_group",
                to="chat.chatroom",
            ),
        ),
    ]

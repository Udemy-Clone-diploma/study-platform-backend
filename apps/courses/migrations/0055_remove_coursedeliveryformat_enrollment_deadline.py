from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0054_merge_20260801_0051"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="coursedeliveryformat",
            name="enrollment_deadline",
        ),
    ]

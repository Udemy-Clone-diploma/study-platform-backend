import apps.common.files
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0013_alter_course_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='lesson',
            name='content',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='lesson',
            name='min_score',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='lesson',
            name='video',
            field=models.FileField(blank=True, null=True, upload_to=apps.common.files.UUIDUploadTo('lessons/videos')),
        ),
    ]

from django.db import migrations, models

from apps.blog.models.Article import default_cover_crops


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0010_translate_blog_categories'),
    ]

    operations = [
        migrations.AddField(
            model_name='article',
            name='cover_crops',
            field=models.JSONField(default=default_cover_crops),
        ),
        migrations.AddField(
            model_name='articlemoderationsnapshot',
            name='cover_crops',
            field=models.JSONField(default=default_cover_crops),
        ),
    ]

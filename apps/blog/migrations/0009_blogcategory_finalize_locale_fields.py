from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0008_backfill_blogcategory_locale_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='blogcategory',
            name='name_en',
            field=models.CharField(max_length=100, unique=True),
        ),
        migrations.AlterField(
            model_name='blogcategory',
            name='headline_en',
            field=models.CharField(max_length=200),
        ),
        migrations.RemoveField(
            model_name='blogcategory',
            name='name',
        ),
        migrations.RemoveField(
            model_name='blogcategory',
            name='headline',
        ),
        migrations.RemoveField(
            model_name='blogcategory',
            name='description',
        ),
        migrations.AlterModelOptions(
            name='blogcategory',
            options={'ordering': ['order', 'name_en'], 'verbose_name': 'blog category', 'verbose_name_plural': 'blog categories'},
        ),
    ]

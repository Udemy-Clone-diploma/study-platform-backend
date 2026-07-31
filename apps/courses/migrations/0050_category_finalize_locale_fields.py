from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0049_backfill_category_locale_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='category',
            name='name_en',
            field=models.CharField(max_length=100, unique=True),
        ),
        migrations.RemoveField(
            model_name='category',
            name='name',
        ),
        migrations.RemoveField(
            model_name='category',
            name='description',
        ),
        migrations.AlterModelOptions(
            name='category',
            options={'ordering': ['name_en'], 'verbose_name': 'category', 'verbose_name_plural': 'categories'},
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0047_course_title_created_at_db_index'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='name_en',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='category',
            name='name_uk',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='category',
            name='name_fr',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='category',
            name='name_es',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='category',
            name='name_de',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='category',
            name='description_en',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='category',
            name='description_uk',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='category',
            name='description_fr',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='category',
            name='description_es',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='category',
            name='description_de',
            field=models.TextField(blank=True, default=''),
        ),
    ]

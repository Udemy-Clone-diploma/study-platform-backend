from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0006_articlemoderationsnapshot'),
    ]

    operations = [
        migrations.AddField(
            model_name='blogcategory',
            name='name_en',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='blogcategory',
            name='name_uk',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='blogcategory',
            name='name_fr',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='blogcategory',
            name='name_es',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='blogcategory',
            name='name_de',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='blogcategory',
            name='headline_en',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='blogcategory',
            name='headline_uk',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='blogcategory',
            name='headline_fr',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='blogcategory',
            name='headline_es',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='blogcategory',
            name='headline_de',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='blogcategory',
            name='description_en',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='blogcategory',
            name='description_uk',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='blogcategory',
            name='description_fr',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='blogcategory',
            name='description_es',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='blogcategory',
            name='description_de',
            field=models.TextField(blank=True, default=''),
        ),
    ]

from django.db import migrations


def backfill_locale_fields(apps, schema_editor):
    BlogCategory = apps.get_model("blog", "BlogCategory")
    for category in BlogCategory.objects.iterator():
        category.name_en = category.name
        category.headline_en = category.headline
        category.description_en = category.description
        category.save(update_fields=["name_en", "headline_en", "description_en"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0007_blogcategory_locale_fields'),
    ]

    operations = [
        migrations.RunPython(backfill_locale_fields, noop),
    ]

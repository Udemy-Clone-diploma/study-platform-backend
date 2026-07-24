from django.db import migrations


def backfill_locale_fields(apps, schema_editor):
    Category = apps.get_model("courses", "Category")
    for category in Category.objects.iterator():
        category.name_en = category.name
        category.description_en = category.description
        category.save(update_fields=["name_en", "description_en"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0048_category_locale_fields'),
    ]

    operations = [
        migrations.RunPython(backfill_locale_fields, noop),
    ]

from django.db import migrations

# Only translates the 5 categories seeded by apps.common.management.commands.seed
# (`_category`). Custom categories an admin created themselves are left alone --
# there's nothing to translate them into.
TRANSLATIONS = {
    "design": {
        "name_uk": "Дизайн",
        "name_fr": "Design",
        "name_es": "Diseño",
        "name_de": "Design",
    },
    "marketing": {
        "name_uk": "Маркетинг",
        "name_fr": "Marketing",
        "name_es": "Marketing",
        "name_de": "Marketing",
    },
    "languages": {
        "name_uk": "Мови",
        "name_fr": "Langues",
        "name_es": "Idiomas",
        "name_de": "Sprachen",
    },
    "it": {
        "name_uk": "ІТ",
        "name_fr": "Informatique",
        "name_es": "TI",
        "name_de": "IT",
    },
    "business": {
        "name_uk": "Бізнес",
        "name_fr": "Affaires",
        "name_es": "Negocios",
        "name_de": "Wirtschaft",
    },
}


def translate_categories(apps, schema_editor):
    Category = apps.get_model("courses", "Category")
    for slug, fields in TRANSLATIONS.items():
        Category.objects.filter(slug=slug).update(**fields)


def untranslate_categories(apps, schema_editor):
    Category = apps.get_model("courses", "Category")
    blank = {f"name_{locale}": "" for locale in ("uk", "fr", "es", "de")}
    Category.objects.filter(slug__in=TRANSLATIONS.keys()).update(**blank)


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0050_category_finalize_locale_fields"),
    ]

    operations = [
        migrations.RunPython(translate_categories, untranslate_categories),
    ]

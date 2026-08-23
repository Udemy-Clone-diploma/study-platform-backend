from django.db import migrations

CATEGORIES = [
    ("Student Stories", "student-stories", "Student stories, career changes, learning experiences"),
    ("Career Growth", "career-growth", "Career advice, skill development, freelancing"),
    ("Design & Creativity", "design-creativity", "UI/UX, graphic design, trends"),
    ("Learning Tips", "learning-tips", "Tips for studying and productivity"),
    ("Industry Insights", "industry-insights", "Industry news and trends"),
    ("Technology", "technology", "AI, digital tools, tech articles"),
    ("Productivity", "productivity", "Work organization, time management"),
    ("Community", "community", "Events, interviews, platform life"),
]


def seed_categories(apps, schema_editor):
    BlogCategory = apps.get_model("blog", "BlogCategory")
    for order, (name, slug, description) in enumerate(CATEGORIES):
        BlogCategory.objects.update_or_create(
            slug=slug,
            defaults={"name": name, "description": description, "order": order},
        )


def unseed_categories(apps, schema_editor):
    BlogCategory = apps.get_model("blog", "BlogCategory")
    BlogCategory.objects.filter(slug__in=[slug for _, slug, _ in CATEGORIES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("blog", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_categories, unseed_categories),
    ]

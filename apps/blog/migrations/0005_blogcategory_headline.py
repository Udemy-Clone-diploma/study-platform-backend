from django.db import migrations, models

HEADLINES = {
    "student-stories": "Stories of growth and new beginnings",
    "career-growth": "Your path to success",
    "design-creativity": "Design Lab",
    "learning-tips": "Study Smart",
    "industry-insights": "What's shaping the industry",
    "technology": "Tools of tomorrow",
    "productivity": "Work smarter, not harder",
    "community": "Life on the platform",
}


def set_headlines(apps, schema_editor):
    BlogCategory = apps.get_model("blog", "BlogCategory")
    for slug, headline in HEADLINES.items():
        BlogCategory.objects.filter(slug=slug).update(headline=headline)


def unset_headlines(apps, schema_editor):
    BlogCategory = apps.get_model("blog", "BlogCategory")
    BlogCategory.objects.filter(slug__in=HEADLINES.keys()).update(headline="")


class Migration(migrations.Migration):

    dependencies = [
        ("blog", "0004_alter_article_cover_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="blogcategory",
            name="headline",
            field=models.CharField(default="", max_length=200),
            preserve_default=False,
        ),
        migrations.RunPython(set_headlines, unset_headlines),
    ]

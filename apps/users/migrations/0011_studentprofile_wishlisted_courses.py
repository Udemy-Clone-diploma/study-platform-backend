from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0001_initial"),
        ("users", "0010_add_social_links_to_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="studentprofile",
            name="wishlisted_courses",
            field=models.ManyToManyField(
                blank=True,
                related_name="wishlisted_by",
                to="courses.course",
            ),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0018_move_test_question_to_curriculum"),
    ]

    operations = [
        migrations.AlterField(
            model_name="course",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("review", "Review"),
                    ("needs_revision", "Needs Revision (returned by moderator)"),
                    ("published", "Published"),
                    ("hidden", "Hidden (active but not listed)"),
                    ("archived", "Archived"),
                ],
                default="draft",
                max_length=20,
            ),
        ),
    ]

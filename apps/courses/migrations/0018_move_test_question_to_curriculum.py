from django.db import migrations


class Migration(migrations.Migration):
    """Detach Test and Question from the courses app at the Django-state level.

    The database tables (`tests`, `questions`) are untouched; the matching
    state-only CreateModel happens in curriculum/0002_add_test_question.py.
    """

    dependencies = [
        ("courses", "0017_merge_0016_branches"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name="test",
                    name="unique_active_test_order_per_module",
                ),
                migrations.DeleteModel(name="Question"),
                migrations.DeleteModel(name="Test"),
            ],
            database_operations=[],
        ),
    ]

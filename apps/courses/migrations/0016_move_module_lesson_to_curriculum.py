from django.db import migrations


class Migration(migrations.Migration):
    """Detach Module and Lesson from the courses app at the Django-state level.

    The database tables (`modules`, `lessons`) are untouched; the matching
    state-only CreateModel happens in curriculum/0001_initial.py.
    """

    dependencies = [
        ("courses", "0015_lesson_body_html_lesson_content_type_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name="lesson",
                    name="unique_active_lesson_order_per_module",
                ),
                migrations.RemoveConstraint(
                    model_name="module",
                    name="unique_active_module_order_per_course",
                ),
                migrations.DeleteModel(name="Lesson"),
                migrations.DeleteModel(name="Module"),
            ],
            database_operations=[],
        ),
    ]

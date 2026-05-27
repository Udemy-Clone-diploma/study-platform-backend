from django.db import migrations


class Migration(migrations.Migration):
    """Ordering anchor after the two 0016 branches were linearised.

    0016_move_module_lesson_to_curriculum now explicitly depends on
    0016_alter_test_passing_score, making it the single 0016 leaf.
    This migration exists so 0018 has a clean predecessor to reference.
    """

    dependencies = [
        ("courses", "0016_move_module_lesson_to_curriculum"),
    ]

    operations = []

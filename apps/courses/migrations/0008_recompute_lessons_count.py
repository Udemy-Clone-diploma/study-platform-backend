from django.db import migrations
from django.db.models import Count


def recompute_lessons_count(apps, schema_editor):
    Course = apps.get_model("courses", "Course")
    Lesson = apps.get_model("courses", "Lesson")

    counts = (
        Lesson.objects.filter(is_deleted=False, module__is_deleted=False)
        .values("module__course_id")
        .annotate(total=Count("id"))
    )
    counts_by_course = {row["module__course_id"]: row["total"] for row in counts}

    for course in Course.objects.all():
        course.lessons_count = counts_by_course.get(course.pk, 0)
        course.save(update_fields=["lessons_count"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0007_module_lesson_and_more"),
    ]

    operations = [
        migrations.RunPython(recompute_lessons_count, noop),
    ]

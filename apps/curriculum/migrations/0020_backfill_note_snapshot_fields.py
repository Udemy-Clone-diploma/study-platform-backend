from django.db import migrations


def backfill_note_snapshot_fields(apps, schema_editor):
    Note = apps.get_model("curriculum", "Note")
    for note in Note.objects.filter(lesson__isnull=False).select_related("lesson__module__course").iterator():
        lesson = note.lesson
        note.course_id = lesson.module.course_id
        note.course_slug = lesson.module.course.slug
        note.course_title = lesson.module.course.title
        note.module_title = lesson.module.title
        note.lesson_title = lesson.title
        note.lesson_order = lesson.order
        note.save(update_fields=[
            "course_id", "course_slug", "course_title",
            "module_title", "lesson_title", "lesson_order",
        ])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('curriculum', '0019_note_course_id_note_course_slug_note_course_title_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_note_snapshot_fields, noop),
    ]

from django.db import migrations


def backfill_note_course_level(apps, schema_editor):
    Note = apps.get_model("curriculum", "Note")
    for note in Note.objects.filter(lesson__isnull=False).select_related("lesson__module__course").iterator():
        note.course_level = note.lesson.module.course.level
        note.save(update_fields=["course_level"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('curriculum', '0021_note_course_level'),
    ]

    operations = [
        migrations.RunPython(backfill_note_course_level, noop),
    ]

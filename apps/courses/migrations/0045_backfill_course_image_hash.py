from django.db import migrations


def backfill_image_hash(apps, schema_editor):
    from apps.common.files import file_content_hash

    Course = apps.get_model("courses", "Course")
    for course in Course.objects.exclude(image="").exclude(image__isnull=True).iterator():
        course.image_hash = file_content_hash(course.image) or ""
        course.save(update_fields=["image_hash"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0044_course_image_hash'),
    ]

    operations = [
        migrations.RunPython(backfill_image_hash, noop),
    ]

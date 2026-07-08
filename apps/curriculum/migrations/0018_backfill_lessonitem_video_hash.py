from django.db import migrations


def backfill_video_hash(apps, schema_editor):
    from apps.common.files import file_content_hash

    LessonItem = apps.get_model("curriculum", "LessonItem")
    for item in LessonItem.objects.exclude(video="").exclude(video__isnull=True).iterator():
        item.video_hash = file_content_hash(item.video) or ""
        item.save(update_fields=["video_hash"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('curriculum', '0017_lessonitem_video_hash'),
    ]

    operations = [
        migrations.RunPython(backfill_video_hash, noop),
    ]

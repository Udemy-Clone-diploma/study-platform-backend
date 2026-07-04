import django.db.models.deletion
from django.db import migrations, models


def delete_existing_pending_edits(apps, schema_editor):
    # The old JSON-snapshot pending edits have no draft_course to backfill —
    # any in-progress edit must be discarded/resubmitted after this migration.
    CoursePendingEdit = apps.get_model("courses", "CoursePendingEdit")
    CoursePendingEdit.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0040_alter_course_image_alter_coursependingedit_image"),
    ]

    operations = [
        migrations.RunPython(delete_existing_pending_edits, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="course",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("review", "Review"),
                    ("needs_revision", "Needs Revision (returned by moderator)"),
                    ("rejected", "Rejected"),
                    ("published", "Published"),
                    ("hidden", "Hidden (active but not listed)"),
                    ("archived", "Archived"),
                    ("pending_edit", "Pending Edit (hidden shadow draft of a published course)"),
                ],
                default="draft",
                max_length=20,
            ),
        ),
        migrations.RemoveField(model_name="coursependingedit", name="category"),
        migrations.RemoveField(model_name="coursependingedit", name="course_type"),
        migrations.RemoveField(model_name="coursependingedit", name="delivery_type"),
        migrations.RemoveField(model_name="coursependingedit", name="duration_hours"),
        migrations.RemoveField(model_name="coursependingedit", name="full_description"),
        migrations.RemoveField(model_name="coursependingedit", name="image"),
        migrations.RemoveField(model_name="coursependingedit", name="is_on_sale"),
        migrations.RemoveField(model_name="coursependingedit", name="language"),
        migrations.RemoveField(model_name="coursependingedit", name="level"),
        migrations.RemoveField(model_name="coursependingedit", name="mode"),
        migrations.RemoveField(model_name="coursependingedit", name="modules_snapshot"),
        migrations.RemoveField(model_name="coursependingedit", name="short_description"),
        migrations.RemoveField(model_name="coursependingedit", name="subtitle"),
        migrations.RemoveField(model_name="coursependingedit", name="tag_ids"),
        migrations.RemoveField(model_name="coursependingedit", name="title"),
        migrations.RemoveField(model_name="coursependingedit", name="with_certificate"),
        migrations.AddField(
            model_name="coursependingedit",
            name="draft_course",
            field=models.OneToOneField(
                default=None,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="as_draft_for",
                to="courses.course",
            ),
            preserve_default=False,
        ),
    ]

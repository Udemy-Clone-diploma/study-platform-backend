import secrets
import uuid

from django.db import migrations

ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"


def _serial(year: int, taken: set[str]) -> str:
    while True:
        candidate = f"CEAT-{year}-" + "".join(secrets.choice(ALPHABET) for _ in range(6))
        if candidate not in taken:
            taken.add(candidate)
            return candidate


def backfill(apps, schema_editor):
    """Give every certificate already in a student's hands a registry row, so
    the admin panel is complete on day one instead of starting empty and only
    filling with certificates issued after this deploy.

    No PDF is re-rendered: the row points at the completion, which already
    stores the exact file the student downloaded.

    Keyed on `certificate_file`, not the older `certificate_url` text column:
    the file is what `Certificate.pdf_file` resolves and what /download/
    serves, so keying on the URL would mint rows with nothing to download.
    """
    CourseCompletion = apps.get_model("enrollments", "CourseCompletion")
    Certificate = apps.get_model("certificates", "Certificate")

    taken = set(Certificate.objects.values_list("serial", flat=True))
    completions = (
        CourseCompletion.objects.exclude(certificate_file__isnull=True)
        .exclude(certificate_file="")
        .select_related("student_profile__user")
    )

    rows = []
    for completion in completions.iterator(chunk_size=500):
        user = completion.student_profile.user
        full_name = f"{user.first_name} {user.last_name}".strip()
        rows.append(
            Certificate(
                serial=_serial(completion.completed_at.year, taken),
                public_uuid=uuid.uuid4(),
                student_profile_id=completion.student_profile_id,
                course_id=completion.course_id,
                completion_id=completion.id,
                student_name=full_name or user.email,
                course_title=completion.title,
                final_score=completion.final_score,
                status="valid",
                issue_reason="completion",
                issued_at=completion.completed_at,
            )
        )

    Certificate.objects.bulk_create(rows, batch_size=500)


class Migration(migrations.Migration):
    dependencies = [
        ("certificates", "0001_initial"),
        ("enrollments", "0008_coursecompletion_certificate_thumbnail"),
    ]

    operations = [
        # Irreversible on purpose: by the time this would be rolled back the
        # table also holds manually issued certificates and revocations, and
        # no rule separates those from the backfilled rows.
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]

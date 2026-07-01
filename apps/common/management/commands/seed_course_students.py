"""Seed 25 test students into a specific course for UI testing.

Usage:
    python manage.py seed_course_students --course <slug>

Distribution:
    - 10 students → group format, Cohort A
    -  6 students → group format, Cohort B
    -  5 students → self-paced format
    -  3 students → scheduled format
    -  1 student  → individual format

Idempotent: get_or_create on every row.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.courses.models import Cohort, CohortMember, Course, CourseDeliveryFormat
from apps.enrollments.models import Enrollment
from apps.users.models import StudentProfile, User

DEMO_PASSWORD = "NovaX1542#"


class Command(BaseCommand):
    help = "Seed 25 test students into a specific course (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--course",
            required=True,
            metavar="SLUG",
            help="Slug of the course to seed students into.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        slug = options["course"]

        try:
            course = Course.all_objects.get(slug=slug)
        except Course.DoesNotExist:
            raise CommandError(f"Course with slug '{slug}' not found.")

        self.stdout.write(f"Seeding students for: {course.title}")

        # --- Delivery formats ------------------------------------------------
        grp_fmt, _ = CourseDeliveryFormat.objects.get_or_create(
            course=course, format_type="group",
        )
        sp_fmt, _ = CourseDeliveryFormat.objects.get_or_create(
            course=course, format_type="self_paced",
        )
        sch_fmt, _ = CourseDeliveryFormat.objects.get_or_create(
            course=course, format_type="scheduled",
        )
        ind_fmt, _ = CourseDeliveryFormat.objects.get_or_create(
            course=course, format_type="individual",
        )

        # --- Cohorts — use existing ones in order of id ----------------------
        existing_cohorts = list(Cohort.objects.filter(course=course).order_by("id"))
        if len(existing_cohorts) < 2:
            raise CommandError(
                f"Course '{slug}' has fewer than 2 cohorts. "
                "Create at least 2 cohorts first."
            )
        cohort_a = existing_cohorts[0]
        cohort_b = existing_cohorts[1]
        self.stdout.write(f"  cohort A → {cohort_a.name or cohort_a.id}")
        self.stdout.write(f"  cohort B → {cohort_b.name or cohort_b.id}")

        # --- Students + enrollments ------------------------------------------
        #  1-10  → group / cohort A
        # 11-16  → group / cohort B
        # 17-21  → self-paced
        # 22-24  → scheduled
        # 25     → individual

        plan = [
            *[(grp_fmt, cohort_a)] * 10,
            *[(grp_fmt, cohort_b)] * 6,
            *[(sp_fmt,  None)]     * 5,
            *[(sch_fmt, None)]     * 3,
            *[(ind_fmt, None)]     * 1,
        ]

        created_count = 0
        for i, (fmt, cohort) in enumerate(plan, start=1):
            email = f"teststudent{i:02d}@example.com"
            user, u_created = User.objects.get_or_create(
                email=email,
                defaults={
                    "role": User.RoleChoices.STUDENT,
                    "first_name": "Test",
                    "last_name": f"Student{i:02d}",
                    "is_email_verified": True,
                },
            )
            if u_created:
                user.set_password(DEMO_PASSWORD)
                user.save()
                created_count += 1

            profile, _ = StudentProfile.objects.get_or_create(user=user)

            enrollment, _ = Enrollment.objects.get_or_create(
                student_profile=profile,
                course=course,
                defaults={
                    "access_status": Enrollment.AccessStatusChoices.ACTIVE,
                    "delivery_format": fmt,
                },
            )

            if cohort:
                CohortMember.objects.get_or_create(
                    cohort=cohort,
                    enrollment=enrollment,
                )

        self.stdout.write(self.style.SUCCESS(
            f"Done. {created_count} new users created. "
            f"25 students enrolled in '{course.title}' "
            f"(10 Group A, 6 Group B, 5 self-paced, 3 scheduled, 1 individual)."
        ))

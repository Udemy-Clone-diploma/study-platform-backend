"""Seed the database with demo data for local development.

Idempotent: every row is created with get_or_create on a natural key, so
running it repeatedly will not duplicate data. Re-run it after a schema reset
(`migrate`) to get a populated dev environment.

    python manage.py seed

All demo users share the password below and are created email-verified, so you
can log in immediately via the auth endpoints.
"""

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.courses.models import Category, Cohort, Course, CourseDeliveryFormat, PricingPlan, Tag
from apps.curriculum.models import Lesson, LessonItem, Module
from apps.enrollments.models import Enrollment, LessonCompletion
from apps.reviews.models import Review
from apps.users.models import (
    ModeratorProfile,
    StudentProfile,
    TeacherProfile,
    User,
)

DEMO_PASSWORD = "Password123!"

# A real HTML blob: full_description is a plain TextField that stores whatever
# string you give it, so the rich-text editor on the frontend can round-trip HTML.
HTML_DESCRIPTION = (
    "<h2>About this course</h2>"
    "<p>Hands-on, project-based learning with real feedback.</p>"
    "<ul><li>Build a portfolio project</li>"
    "<li>Weekly live sessions</li>"
    "<li>Certificate on completion</li></ul>"
)


class Command(BaseCommand):
    help = "Seed the database with demo data for local development (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Seeding demo data...")

        # --- Users + role-specific profiles -------------------------------
        self._user("admin@example.com", User.RoleChoices.ADMINISTRATOR, "Ada", "Admin",
                   is_staff=True, is_superuser=True)

        moderators = [
            self._moderator(self._user(f"moderator{i}@example.com",
                                       User.RoleChoices.MODERATOR, "Mod", f"Erator{i}"),
                            level="senior" if i == 1 else "junior")
            for i in (1, 2)
        ]

        teachers = [
            self._teacher(self._user(f"teacher{i}@example.com",
                                     User.RoleChoices.TEACHER, "Tessa", f"Teach{i}"),
                          specialization=spec)
            for i, spec in ((1, "Backend"), (2, "Frontend"), (3, "Design"))
        ]

        students = [
            self._student(self._user(f"student{i}@example.com",
                                     User.RoleChoices.STUDENT, "Stu", f"Dent{i}"))
            for i in range(1, 6)
        ]

        # --- Taxonomy -----------------------------------------------------
        cats = {name: self._category(name) for name in
                ("Programming", "Design", "Data", "Marketing")}
        tags = {name: self._tag(name) for name in
                ("python", "django", "react", "ux", "analytics", "beginner-friendly")}

        # --- Courses ------------------------------------------------------
        # Published, with teacher, scheduled, full curriculum + payments + cohorts.
        django_course = self._course(
            slug="backend-engineering-django",
            title="Backend Engineering with Django",
            subtitle="From zero to a deployed REST API",
            teacher=teachers[0], category=cats["Programming"],
            tags=[tags["python"], tags["django"], tags["beginner-friendly"]],
            course_type=Course.CourseTypeChoices.PROFESSION,
            level=Course.LevelChoices.BEGINNER,
            mode=Course.ModeChoices.WITH_TEACHER,
            delivery_type=Course.DeliveryTypeChoices.SCHEDULED,
            status=Course.StatusChoices.PUBLISHED,
            with_certificate=True, is_on_sale=True, duration_hours=60,
        )
        self._curriculum(django_course, with_meeting=True)
        grp_fmt_django = self._format_with_price(
            django_course, "group", Decimal("149.99"), "USD",
            installment_count=4, installment_amount=Decimal("40.00"),
        )
        ind_fmt_django = self._format_with_price(django_course, "individual", Decimal("299.00"), "USD")
        self._cohort(django_course, 3, 5, group_size=15, days_ahead=30, delivery_format=grp_fmt_django)
        self._cohort(django_course, 4, 4, days_ahead=14)
        self._enroll(students[0], django_course, completed=2, delivery_format=grp_fmt_django)
        self._enroll(students[1], django_course, completed=1, delivery_format=grp_fmt_django)
        self._enroll(students[2], django_course, completed=0, delivery_format=ind_fmt_django)
        self._review(django_course, students[0].user, 5, "Best Django course I have taken.")
        self._review(django_course, students[1].user, 4, "Very practical, dense in a good way.")

        # Published, self-paced, EUR pricing.
        react_course = self._course(
            slug="react-from-scratch",
            title="React from Scratch",
            subtitle="Components, hooks, and state done right",
            teacher=teachers[1], category=cats["Programming"],
            tags=[tags["react"], tags["beginner-friendly"]],
            course_type=Course.CourseTypeChoices.PROFESSION,
            level=Course.LevelChoices.INTERMEDIATE,
            mode=Course.ModeChoices.SELF_LEARNING,
            delivery_type=Course.DeliveryTypeChoices.SELF_PACED,
            status=Course.StatusChoices.PUBLISHED,
            with_certificate=True, duration_hours=35,
        )
        self._curriculum(react_course)
        sp_fmt_react = self._format_with_price(react_course, "self_paced", Decimal("120.00"), "EUR")
        self._enroll(students[1], react_course, completed=3, delivery_format=sp_fmt_react)
        self._enroll(students[3], react_course, completed=0, delivery_format=sp_fmt_react)
        self._review(react_course, students[1].user, 5, "Clicked for me finally.")

        # Published, individual delivery, UAH pricing with installments.
        ux_course = self._course(
            slug="ux-design-fundamentals",
            title="UX Design Fundamentals",
            subtitle="Research, wireframes, and usable interfaces",
            teacher=teachers[2], category=cats["Design"],
            tags=[tags["ux"], tags["beginner-friendly"]],
            course_type=Course.CourseTypeChoices.KNOWLEDGE,
            level=Course.LevelChoices.BEGINNER,
            mode=Course.ModeChoices.WITH_TEACHER,
            delivery_type=Course.DeliveryTypeChoices.GROUP,
            status=Course.StatusChoices.PUBLISHED,
            duration_hours=24,
        )
        self._curriculum(ux_course, with_meeting=True)
        self._format_with_price(
            ux_course, "individual", Decimal("5000.00"), "UAH",
            installment_count=5, installment_amount=Decimal("1100.00"),
        )
        grp_fmt_ux = self._format_with_price(ux_course, "group", Decimal("3000.00"), "UAH")
        self._cohort(ux_course, 2, 6, group_size=12, days_ahead=21, delivery_format=grp_fmt_ux)
        self._enroll(students[4], ux_course, completed=1, delivery_format=grp_fmt_ux)
        self._review(ux_course, students[4].user, 4, "Loved the hands-on critiques.")

        # Published qualification course, USD.
        data_course = self._course(
            slug="data-analysis-bootcamp",
            title="Data Analysis Bootcamp",
            subtitle="From spreadsheets to dashboards",
            teacher=teachers[0], category=cats["Data"],
            tags=[tags["python"], tags["analytics"]],
            course_type=Course.CourseTypeChoices.QUALIFICATION,
            level=Course.LevelChoices.ADVANCED,
            mode=Course.ModeChoices.WITH_TEACHER,
            delivery_type=Course.DeliveryTypeChoices.SCHEDULED,
            status=Course.StatusChoices.PUBLISHED,
            with_certificate=True, duration_hours=50,
        )
        self._curriculum(data_course)
        grp_fmt_data = self._format_with_price(data_course, "group", Decimal("199.00"), "USD")
        self._cohort(data_course, 3, 5, group_size=20, days_ahead=60, delivery_format=grp_fmt_data)
        self._enroll(students[2], data_course, completed=0, delivery_format=grp_fmt_data)
        self._enroll(students[3], data_course, completed=2, delivery_format=grp_fmt_data)

        # Non-published states so moderation flows have data to show.
        self._course(
            slug="advanced-kubernetes", title="Advanced Kubernetes",
            subtitle="Operators, scaling, and observability",
            teacher=teachers[1], category=cats["Programming"], tags=[tags["python"]],
            course_type=Course.CourseTypeChoices.PROFESSION,
            level=Course.LevelChoices.ADVANCED, mode=Course.ModeChoices.SELF_LEARNING,
            delivery_type=Course.DeliveryTypeChoices.SELF_PACED,
            status=Course.StatusChoices.DRAFT, duration_hours=40,
        )
        self._course(
            slug="marketing-essentials", title="Marketing Essentials",
            subtitle="Channels, funnels, and metrics",
            teacher=teachers[2], category=cats["Marketing"], tags=[tags["beginner-friendly"]],
            course_type=Course.CourseTypeChoices.KNOWLEDGE,
            level=Course.LevelChoices.BEGINNER, mode=Course.ModeChoices.WITH_TEACHER,
            delivery_type=Course.DeliveryTypeChoices.GROUP,
            status=Course.StatusChoices.REVIEW, duration_hours=18,
            moderator=moderators[0],
        )
        self._course(
            slug="photography-basics", title="Photography Basics",
            subtitle="Light, composition, and editing",
            teacher=teachers[0], category=cats["Design"], tags=[tags["beginner-friendly"]],
            course_type=Course.CourseTypeChoices.KNOWLEDGE,
            level=Course.LevelChoices.BEGINNER, mode=Course.ModeChoices.SELF_LEARNING,
            delivery_type=Course.DeliveryTypeChoices.SELF_PACED,
            status=Course.StatusChoices.NEEDS_REVISION, duration_hours=12,
            moderator_comment="Please add a syllabus and at least one preview lesson.",
        )

        self.stdout.write(self.style.SUCCESS(
            f"Done. {User.objects.count()} users, {Course.all_objects.count()} courses, "
            f"{Enrollment.objects.count()} enrollments. Demo password: {DEMO_PASSWORD!r}"
        ))

    # --- helpers ----------------------------------------------------------

    def _user(self, email, role, first, last, **extra):
        user, created = User.objects.get_or_create(
            email=email,
            defaults={"role": role, "first_name": first, "last_name": last,
                      "is_email_verified": True, **extra},
        )
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save()
        return user

    def _student(self, user):
        return StudentProfile.objects.get_or_create(user=user)[0]

    def _teacher(self, user, specialization=""):
        return TeacherProfile.objects.get_or_create(
            user=user, defaults={"specialization": specialization,
                                 "bio": "Practitioner and mentor."})[0]

    def _moderator(self, user, level="junior"):
        return ModeratorProfile.objects.get_or_create(
            user=user, defaults={"level": level})[0]

    def _category(self, name):
        from django.utils.text import slugify
        return Category.objects.get_or_create(
            slug=slugify(name), defaults={"name": name})[0]

    def _tag(self, name):
        return Tag.objects.get_or_create(name=name)[0]

    def _course(self, *, slug, title, subtitle, teacher, category, tags,
                course_type, level, mode, delivery_type, status, duration_hours,
                with_certificate=False, is_on_sale=False, moderator=None,
                moderator_comment=""):
        published_at = timezone.now() if status == Course.StatusChoices.PUBLISHED else None
        course, _ = Course.all_objects.get_or_create(
            slug=slug,
            defaults={
                "title": title, "subtitle": subtitle,
                "short_description": subtitle,
                "full_description": HTML_DESCRIPTION,
                "teacher_profile": teacher, "category": category,
                "moderator_profile": moderator,
                "course_type": course_type, "level": level, "mode": mode,
                "delivery_type": delivery_type, "status": status,
                "duration_hours": duration_hours,
                "with_certificate": with_certificate, "is_on_sale": is_on_sale,
                "moderator_comment": moderator_comment,
                "published_at": published_at,
            },
        )
        course.tags.set(tags)
        return course

    def _curriculum(self, course, with_meeting=False):
        """Two modules, three lessons each (video + text, first one preview)."""
        for m_order in (1, 2):
            module, _ = Module.objects.get_or_create(
                course=course, order=m_order,
                defaults={"title": f"Module {m_order}",
                          "description": "What you will build in this module."},
            )
            for l_order in (1, 2, 3):
                is_text = l_order == 3
                lesson, _ = Lesson.objects.get_or_create(
                    module=module, order=l_order,
                    defaults={
                        "title": f"Lesson {m_order}.{l_order}",
                        "duration_minutes": 12 + l_order,
                        "is_preview": m_order == 1 and l_order == 1,
                        "meeting_url": ("https://meet.example.com/live"
                                        if with_meeting and not is_text else None),
                    },
                )
                if is_text:
                    LessonItem.objects.get_or_create(
                        lesson=lesson, order=1,
                        defaults={
                            "item_type": LessonItem.ItemType.TEXT,
                            "content": "Read-along lesson notes.",
                            "body_html": "<p>Read-along lesson notes.</p>",
                        },
                    )
                else:
                    LessonItem.objects.get_or_create(
                        lesson=lesson, order=1,
                        defaults={
                            "item_type": LessonItem.ItemType.VIDEO,
                            "video_url": "https://example.com/video.mp4",
                            "duration_minutes": 12 + l_order,
                        },
                    )

    def _format_with_price(self, course, format_type, price, currency,
                            installment_count=None, installment_amount=None):
        fmt, _ = CourseDeliveryFormat.objects.get_or_create(
            course=course, format_type=format_type,
        )
        PricingPlan.objects.update_or_create(
            delivery_format=fmt,
            defaults={"price": price, "currency": currency,
                      "installment_count": installment_count,
                      "installment_amount": installment_amount},
        )
        return fmt

    def _cohort(self, course, months, hours_per_week,
                group_size=None, days_ahead=30, delivery_format=None):
        start = (timezone.now() + timedelta(days=days_ahead)).date()
        return Cohort.objects.get_or_create(
            course=course, start_date=start,
            defaults={"duration_months": months, "hours_per_week": hours_per_week,
                      "group_size": group_size, "delivery_format": delivery_format},
        )[0]

    def _enroll(self, student, course, completed=0, delivery_format=None):
        enrollment, created = Enrollment.objects.get_or_create(
            student_profile=student, course=course,
            defaults={"access_status": Enrollment.AccessStatusChoices.ACTIVE,
                      "delivery_format": delivery_format},
        )
        if not created and delivery_format and enrollment.delivery_format_id is None:
            enrollment.delivery_format = delivery_format
            enrollment.save(update_fields=["delivery_format"])
        if completed:
            lessons = list(Lesson.objects.filter(module__course=course).order_by(
                "module__order", "order")[:completed])
            for lesson in lessons:
                LessonCompletion.objects.get_or_create(enrollment=enrollment, lesson=lesson)
        return enrollment

    def _review(self, course, user, rating, text):
        return Review.objects.get_or_create(
            course=course, student=user,
            defaults={"rating": rating, "text": text},
        )[0]

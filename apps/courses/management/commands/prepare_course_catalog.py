"""Repair legacy course data and seed a stable demo catalog.

The command is intentionally idempotent. It can be run after migrations or a
database restore without duplicating teachers, students, courses, formats,
pricing, cohorts, modules, lessons, enrollments, or reviews.

Examples:

    python manage.py prepare_course_catalog --image /path/to/course.png
    python manage.py prepare_course_catalog --check-only
"""

from collections import Counter
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Avg, Count
from django.utils import timezone

from apps.courses.models import (
    Category,
    Cohort,
    Course,
    CourseDeliveryFormat,
    PricingPlan,
)
from apps.curriculum.models import Lesson, Module
from apps.enrollments.models import Enrollment
from apps.reviews.models import Review
from apps.users.models import StudentProfile, TeacherProfile, User

CATEGORY_SPECS = {
    "design": {
        "name_en": "Design",
        "description_en": "UX, UI, product design, and creative practice.",
        "featured_order": 0,
    },
    "business": {
        "name_en": "Business",
        "description_en": "Leadership, communication, and career growth.",
        "featured_order": 1,
    },
    "python": {
        "name_en": "Python",
        "description_en": "Python programming and backend engineering.",
        "featured_order": 2,
    },
}

TEACHER_SPECS = {
    "jordan@example.com": {
        "first_name": "Jordan",
        "last_name": "Peterson",
        "specialization": "Business psychology and leadership",
        "bio": "Teacher and mentor focused on leadership, communication, and decision-making.",
        "years_experience": 15,
    },
    "sophia.martinez@example.com": {
        "first_name": "Sophia",
        "last_name": "Martinez",
        "specialization": "UX research and product design",
        "bio": (
            "Product designer helping students turn research into clear, "
            "accessible interfaces."
        ),
        "years_experience": 9,
    },
    "liam.anderson@example.com": {
        "first_name": "Liam",
        "last_name": "Anderson",
        "specialization": "Python and backend development",
        "bio": "Backend engineer teaching practical Python, Django, and software architecture.",
        "years_experience": 11,
    },
}

REVIEWER_SPECS = {
    "emily.watson@example.com": ("Emily", "Watson"),
    "marcus.nilsson@example.com": ("Marcus", "Nilsson"),
    "amara.okafor@example.com": ("Amara", "Okafor"),
    "lucas.wojcik@example.com": ("Lucas", "Wojcik"),
    "olivia.novak@example.com": ("Olivia", "Novak"),
}

COURSE_SPECS = [
    {
        "slug": "leadership-psychology-in-practice",
        "title": "Leadership Psychology in Practice",
        "teacher": "jordan@example.com",
        "category": "business",
        "level": Course.LevelChoices.INTERMEDIATE,
        "delivery_type": Course.DeliveryTypeChoices.SELF_PACED,
        "price": Decimal("79.00"),
        "is_on_sale": True,
        "discount_percent": 20,
    },
    {
        "slug": "critical-thinking-better-decisions",
        "title": "Critical Thinking and Better Decisions",
        "teacher": "jordan@example.com",
        "category": "business",
        "level": Course.LevelChoices.BEGINNER,
        "delivery_type": Course.DeliveryTypeChoices.SELF_PACED,
        "price": Decimal("59.00"),
    },
    {
        "slug": "communication-that-builds-trust",
        "title": "Communication That Builds Trust",
        "teacher": "jordan@example.com",
        "category": "business",
        "level": Course.LevelChoices.INTERMEDIATE,
        "delivery_type": Course.DeliveryTypeChoices.SCHEDULED,
        "price": Decimal("89.00"),
    },
    {
        "slug": "ux-research-fundamentals",
        "title": "UX Research Fundamentals",
        "teacher": "sophia.martinez@example.com",
        "category": "design",
        "level": Course.LevelChoices.BEGINNER,
        "delivery_type": Course.DeliveryTypeChoices.SELF_PACED,
        "price": Decimal("69.00"),
    },
    {
        "slug": "design-systems-from-scratch",
        "title": "Design Systems from Scratch",
        "teacher": "sophia.martinez@example.com",
        "category": "design",
        "level": Course.LevelChoices.INTERMEDIATE,
        "delivery_type": Course.DeliveryTypeChoices.SCHEDULED,
        "price": Decimal("99.00"),
    },
    {
        "slug": "product-design-portfolio-lab",
        "title": "Product Design Portfolio Lab",
        "teacher": "sophia.martinez@example.com",
        "category": "design",
        "level": Course.LevelChoices.ADVANCED,
        "delivery_type": Course.DeliveryTypeChoices.GROUP,
        "price": Decimal("149.00"),
    },
    {
        "slug": "python-real-world-automation",
        "title": "Python for Real-World Automation",
        "teacher": "liam.anderson@example.com",
        "category": "python",
        "level": Course.LevelChoices.BEGINNER,
        "delivery_type": Course.DeliveryTypeChoices.SELF_PACED,
        "price": Decimal("79.00"),
    },
    {
        "slug": "advanced-python-architecture",
        "title": "Advanced Python Architecture",
        "teacher": "liam.anderson@example.com",
        "category": "python",
        "level": Course.LevelChoices.ADVANCED,
        "delivery_type": Course.DeliveryTypeChoices.INDIVIDUAL,
        "price": Decimal("199.00"),
    },
    {
        "slug": "building-apis-with-django",
        "title": "Building APIs with Django",
        "teacher": "liam.anderson@example.com",
        "category": "python",
        "level": Course.LevelChoices.INTERMEDIATE,
        "delivery_type": Course.DeliveryTypeChoices.GROUP,
        "price": Decimal("159.00"),
    },
]

REVIEW_SPECS = {
    "ux-research-fundamentals": [
        (
            "emily.watson@example.com",
            5,
            "The research framework made interviews and usability testing feel practical. "
            "I used the templates in a portfolio project and finally understood how to "
            "turn observations into clear product decisions.",
        ),
        (
            "marcus.nilsson@example.com",
            5,
            "Clear explanations, realistic exercises, and a very useful structure. The "
            "course helped me collaborate with designers without getting lost in jargon.",
        ),
        (
            "amara.okafor@example.com",
            5,
            "The strongest part is the practical feedback. Every lesson connects research "
            "to a decision you would actually make on a product team.",
        ),
        (
            "lucas.wojcik@example.com",
            4,
            "A focused introduction with enough depth to apply immediately. The interview "
            "planning and synthesis sections were especially valuable.",
        ),
        (
            "olivia.novak@example.com",
            5,
            "I came in with no formal UX research process and left with a repeatable one. "
            "The final project tied all the techniques together nicely.",
        ),
    ],
    "leadership-psychology-in-practice": [
        (
            "emily.watson@example.com",
            5,
            "Jordan turns abstract psychology into concrete conversations and decisions. "
            "The reflection exercises immediately improved my weekly team meetings.",
        ),
        (
            "amara.okafor@example.com",
            4,
            "Thoughtful, structured, and refreshingly practical. I would recommend it to "
            "anyone leading a team for the first time.",
        ),
        (
            "lucas.wojcik@example.com",
            5,
            "The course gave me a much clearer way to handle conflict and give feedback "
            "without making people defensive.",
        ),
        (
            "olivia.novak@example.com",
            5,
            "Excellent examples and a good pace. The section on trust changed how I prepare "
            "for difficult one-to-one conversations.",
        ),
    ],
    "python-real-world-automation": [
        (
            "marcus.nilsson@example.com",
            5,
            "The projects are small enough to finish but useful enough to keep. I automated "
            "two repetitive reporting tasks before completing the course.",
        ),
        (
            "amara.okafor@example.com",
            4,
            "A friendly path from Python basics to scripts that solve real work problems. "
            "The error-handling examples were particularly helpful.",
        ),
        (
            "lucas.wojcik@example.com",
            5,
            "Liam explains not only what to type but why the code is structured that way. "
            "That made the final automation project much easier to extend.",
        ),
        (
            "olivia.novak@example.com",
            5,
            "Well-paced lessons, useful exercises, and no filler. It is a strong first course "
            "for anyone who wants Python to save time in everyday work.",
        ),
    ],
}

DEFAULT_PRICES = {
    CourseDeliveryFormat.FormatType.SELF_PACED: Decimal("49.00"),
    CourseDeliveryFormat.FormatType.SCHEDULED: Decimal("79.00"),
    CourseDeliveryFormat.FormatType.GROUP: Decimal("149.00"),
    CourseDeliveryFormat.FormatType.INDIVIDUAL: Decimal("199.00"),
}


class Command(BaseCommand):
    help = "Repair legacy course data, seed demo teachers/courses, and validate catalog integrity."

    def add_arguments(self, parser):
        parser.add_argument(
            "--image",
            type=Path,
            help="Optional image copied into every active course that has no image.",
        )
        parser.add_argument(
            "--check-only",
            action="store_true",
            help="Validate the current catalog without changing the database.",
        )

    def handle(self, *args, **options):
        if options["check_only"]:
            self._report_validation()
            return

        image_path = options.get("image")
        if image_path and not image_path.is_file():
            raise CommandError(f"Course image not found: {image_path}")

        stats = Counter()
        with transaction.atomic():
            categories = self._ensure_categories(stats)
            teachers = self._ensure_teachers(stats)
            reviewers = self._ensure_reviewers(stats)

            for course in Course.objects.select_related("category", "teacher_profile__user"):
                self._repair_course(course, categories, image_path, stats)

            for index, spec in enumerate(COURSE_SPECS):
                course = self._ensure_demo_course(
                    spec,
                    teachers,
                    categories,
                    image_path,
                    index,
                    stats,
                )
                self._ensure_curriculum(course, stats)
                if spec["delivery_type"] == Course.DeliveryTypeChoices.GROUP:
                    self._ensure_demo_cohort(course, stats)

            self._ensure_demo_reviews(reviewers, stats)

            errors, warnings = self._catalog_issues()
            if errors:
                raise CommandError(self._format_issues("Catalog repair failed", errors))

        self.stdout.write(
            self.style.SUCCESS(
                "Catalog prepared: "
                f"{stats['teachers_created']} teachers created, "
                f"{stats['students_created']} students created, "
                f"{stats['courses_created']} courses created, "
                f"{stats['courses_repaired']} existing courses repaired, "
                f"{stats['formats_created']} formats created, "
                f"{stats['pricing_created']} pricing plans created, "
                f"{stats['covers_assigned']} covers assigned, "
                f"{stats['reviews_created']} reviews created."
            )
        )
        for warning in warnings:
            self.stdout.write(self.style.WARNING(f"WARNING: {warning}"))

    def _ensure_categories(self, stats):
        categories = {}
        for slug, defaults in CATEGORY_SPECS.items():
            category, created = Category.all_objects.get_or_create(
                slug=slug,
                defaults=defaults,
            )
            changed_fields = []
            if category.is_deleted:
                category.is_deleted = False
                changed_fields.append("is_deleted")
            if category.featured_order is None:
                category.featured_order = defaults["featured_order"]
                changed_fields.append("featured_order")
            if changed_fields:
                category.save(update_fields=changed_fields)
            if created:
                stats["categories_created"] += 1
            categories[slug] = category
        return categories

    def _ensure_teachers(self, stats):
        teachers = {}
        for email, spec in TEACHER_SPECS.items():
            user, created = User.all_objects.get_or_create(
                email=email,
                defaults={
                    "first_name": spec["first_name"],
                    "last_name": spec["last_name"],
                    "role": User.RoleChoices.TEACHER,
                    "status": User.StatusChoices.ACTIVE,
                    "is_email_verified": True,
                },
            )
            if created:
                user.set_unusable_password()
                user.save(update_fields=["password"])
                stats["teachers_created"] += 1
            else:
                changed_fields = []
                expected = {
                    "first_name": spec["first_name"],
                    "last_name": spec["last_name"],
                    "role": User.RoleChoices.TEACHER,
                    "status": User.StatusChoices.ACTIVE,
                    "is_email_verified": True,
                    "is_deleted": False,
                    "is_blocked": False,
                }
                for field, value in expected.items():
                    if getattr(user, field) != value:
                        setattr(user, field, value)
                        changed_fields.append(field)
                if changed_fields:
                    user.save(update_fields=changed_fields)

            profile, _ = TeacherProfile.objects.get_or_create(
                user=user,
                defaults={
                    "specialization": spec["specialization"],
                    "bio": spec["bio"],
                    "experience": spec["bio"],
                    "years_experience": spec["years_experience"],
                },
            )
            profile_fields = []
            for field in ("specialization", "bio", "experience", "years_experience"):
                if not getattr(profile, field):
                    value = spec["bio"] if field == "experience" else spec[field]
                    setattr(profile, field, value)
                    profile_fields.append(field)
            if profile_fields:
                profile.save(update_fields=profile_fields)
            teachers[email] = profile
        return teachers

    def _ensure_reviewers(self, stats):
        reviewers = {}
        for email, (first_name, last_name) in REVIEWER_SPECS.items():
            user, created = User.all_objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "role": User.RoleChoices.STUDENT,
                    "status": User.StatusChoices.ACTIVE,
                    "is_email_verified": True,
                },
            )
            if created:
                user.set_unusable_password()
                user.save(update_fields=["password"])
                stats["students_created"] += 1
            else:
                changed_fields = []
                expected = {
                    "first_name": first_name,
                    "last_name": last_name,
                    "role": User.RoleChoices.STUDENT,
                    "status": User.StatusChoices.ACTIVE,
                    "is_email_verified": True,
                    "is_deleted": False,
                    "is_blocked": False,
                }
                for field, value in expected.items():
                    if getattr(user, field) != value:
                        setattr(user, field, value)
                        changed_fields.append(field)
                if changed_fields:
                    user.save(update_fields=changed_fields)

            profile, _ = StudentProfile.objects.get_or_create(user=user)
            reviewers[email] = (user, profile)
        return reviewers

    def _ensure_demo_reviews(self, reviewers, stats):
        for course_slug, review_specs in REVIEW_SPECS.items():
            course = Course.objects.get(slug=course_slug)
            delivery_format = course.delivery_formats.filter(
                format_type=course.delivery_type,
            ).first()
            for email, rating, review_text in review_specs:
                user, profile = reviewers[email]
                enrollment, _ = Enrollment.all_objects.get_or_create(
                    student_profile=profile,
                    course=course,
                    defaults={"delivery_format": delivery_format},
                )
                enrollment_fields = []
                if enrollment.is_deleted:
                    enrollment.is_deleted = False
                    enrollment_fields.append("is_deleted")
                if enrollment.access_status != Enrollment.AccessStatusChoices.ACTIVE:
                    enrollment.access_status = Enrollment.AccessStatusChoices.ACTIVE
                    enrollment_fields.append("access_status")
                if enrollment.delivery_format_id is None and delivery_format is not None:
                    enrollment.delivery_format = delivery_format
                    enrollment_fields.append("delivery_format")
                if enrollment_fields:
                    enrollment.save(update_fields=enrollment_fields)

                _, created = Review.all_objects.update_or_create(
                    course=course,
                    student=user,
                    defaults={
                        "rating": rating,
                        "text": review_text,
                        "moderator_profile": None,
                        "moderation_status": "",
                        "moderation_assigned_at": None,
                        "moderated_at": None,
                        "is_deleted": False,
                    },
                )
                if created:
                    stats["reviews_created"] += 1

    def _repair_course(self, course, categories, image_path, stats):
        changed_fields = []
        if course.category_id is None:
            category_slugs = tuple(categories)
            course.category = categories[category_slugs[course.pk % len(category_slugs)]]
            changed_fields.append("category")

        if not (course.short_description or "").strip() or len(
            course.short_description.strip()
        ) < 20:
            course.short_description = (
                f"A practical {course.title} course with guided examples and hands-on exercises."
            )
            changed_fields.append("short_description")
        if not (course.full_description or "").strip() or len(
            course.full_description.strip()
        ) < 50:
            course.full_description = (
                f"Build a solid understanding of {course.title} through clear explanations, "
                "guided practice, and realistic projects. The course is structured to help "
                "students apply every concept and track measurable progress."
            )
            changed_fields.append("full_description")

        expected_mode = (
            Course.ModeChoices.SELF_LEARNING
            if course.delivery_type
            in (
                Course.DeliveryTypeChoices.SELF_PACED,
                Course.DeliveryTypeChoices.SCHEDULED,
            )
            else Course.ModeChoices.WITH_TEACHER
        )
        if course.mode != expected_mode:
            course.mode = expected_mode
            changed_fields.append("mode")

        if course.status == Course.StatusChoices.PUBLISHED and course.published_at is None:
            course.published_at = course.created_at or timezone.now()
            changed_fields.append("published_at")
        if course.is_on_sale and not course.discount_percent:
            course.discount_percent = 15
            changed_fields.append("discount_percent")
        if not course.is_on_sale and course.discount_percent is not None:
            course.discount_percent = None
            changed_fields.append("discount_percent")

        review_aggregates = Review.objects.filter(course=course).aggregate(
            average=Avg("rating"),
            count=Count("id"),
        )
        expected_rating_count = review_aggregates["count"] or 0
        expected_rating_avg = review_aggregates["average"] or Decimal("0.00")
        if course.rating_count != expected_rating_count:
            course.rating_count = expected_rating_count
            changed_fields.append("rating_count")
        if course.rating_avg != expected_rating_avg:
            course.rating_avg = expected_rating_avg
            changed_fields.append("rating_avg")

        if changed_fields:
            course.save(update_fields=changed_fields)
            stats["courses_repaired"] += 1

        if image_path and not course.image:
            self._assign_image(course, image_path)
            stats["covers_assigned"] += 1

        self._ensure_format(course, course.delivery_type, stats)
        for delivery_format in course.delivery_formats.all():
            self._configure_format(delivery_format)
            self._ensure_pricing(delivery_format, stats)

        if course.cohorts.exists():
            group_format = self._ensure_format(
                course,
                CourseDeliveryFormat.FormatType.GROUP,
                stats,
            )
            self._repair_cohorts(course, group_format, stats)

        if (
            course.status == Course.StatusChoices.PUBLISHED
            and not course.modules.exists()
        ):
            self._ensure_curriculum(course, stats)

    def _ensure_demo_course(
        self,
        spec,
        teachers,
        categories,
        image_path,
        index,
        stats,
    ):
        published_at = timezone.now() - timedelta(days=index + 1)
        mode = (
            Course.ModeChoices.SELF_LEARNING
            if spec["delivery_type"]
            in (
                Course.DeliveryTypeChoices.SELF_PACED,
                Course.DeliveryTypeChoices.SCHEDULED,
            )
            else Course.ModeChoices.WITH_TEACHER
        )
        defaults = {
            "title": spec["title"],
            "subtitle": "Practical skills you can apply immediately",
            "short_description": (
                f"Learn {spec['title'].lower()} through clear explanations and practical work."
            ),
            "full_description": (
                f"This hands-on course develops real confidence in {spec['title'].lower()}. "
                "Each section combines concise theory, guided examples, and practical tasks "
                "that can be applied in professional projects."
            ),
            "teacher_profile": teachers[spec["teacher"]],
            "category": categories[spec["category"]],
            "level": spec["level"],
            "language": Course.LanguageChoices.ENGLISH,
            "mode": mode,
            "delivery_type": spec["delivery_type"],
            "course_type": Course.CourseTypeChoices.KNOWLEDGE,
            "with_certificate": False,
            "is_on_sale": spec.get("is_on_sale", False),
            "discount_percent": spec.get("discount_percent"),
            "status": Course.StatusChoices.PUBLISHED,
            "published_at": published_at,
        }
        course, created = Course.all_objects.get_or_create(
            slug=spec["slug"],
            defaults=defaults,
        )
        if created:
            stats["courses_created"] += 1
        else:
            restore_fields = []
            if course.is_deleted:
                course.is_deleted = False
                restore_fields.append("is_deleted")
            if course.status != Course.StatusChoices.PUBLISHED:
                course.status = Course.StatusChoices.PUBLISHED
                restore_fields.append("status")
            if course.published_at is None:
                course.published_at = published_at
                restore_fields.append("published_at")
            if restore_fields:
                course.save(update_fields=restore_fields)

        if image_path and not course.image:
            self._assign_image(course, image_path)
            stats["covers_assigned"] += 1

        delivery_format = self._ensure_format(course, spec["delivery_type"], stats)
        PricingPlan.objects.update_or_create(
            delivery_format=delivery_format,
            defaults={
                "price": spec["price"],
                "currency": PricingPlan.CurrencyChoices.USD,
            },
        )
        return course

    def _ensure_format(self, course, format_type, stats):
        delivery_format, created = CourseDeliveryFormat.objects.get_or_create(
            course=course,
            format_type=format_type,
            defaults=self._format_defaults(format_type),
        )
        if created:
            stats["formats_created"] += 1
        self._configure_format(delivery_format)
        self._ensure_pricing(delivery_format, stats)
        return delivery_format

    def _format_defaults(self, format_type):
        today = timezone.localdate()
        if format_type == CourseDeliveryFormat.FormatType.SELF_PACED:
            return {
                "start_type": CourseDeliveryFormat.StartType.MANUAL,
                "access_duration_days": 0,
            }
        if format_type in (
            CourseDeliveryFormat.FormatType.SCHEDULED,
            CourseDeliveryFormat.FormatType.GROUP,
        ):
            return {
                "start_date": today + timedelta(days=30),
                "unlock_mode": CourseDeliveryFormat.UnlockMode.SEQUENTIAL,
            }
        return {"max_students": 20}

    def _configure_format(self, delivery_format):
        defaults = self._format_defaults(delivery_format.format_type)
        changed_fields = []
        for field, value in defaults.items():
            current = getattr(delivery_format, field)
            if current is None:
                setattr(delivery_format, field, value)
                changed_fields.append(field)
        if changed_fields:
            delivery_format.save(update_fields=changed_fields)

    def _ensure_pricing(self, delivery_format, stats):
        _, created = PricingPlan.objects.get_or_create(
            delivery_format=delivery_format,
            defaults={
                "price": DEFAULT_PRICES[delivery_format.format_type],
                "currency": PricingPlan.CurrencyChoices.USD,
            },
        )
        if created:
            stats["pricing_created"] += 1

    def _repair_cohorts(self, course, group_format, stats):
        today = timezone.localdate()
        for cohort in course.cohorts.all():
            changed_fields = []
            if cohort.delivery_format_id != group_format.pk:
                cohort.delivery_format = group_format
                changed_fields.append("delivery_format")
            if not cohort.name:
                cohort.name = f"{course.title} group {cohort.pk}"
                changed_fields.append("name")
            if not cohort.duration_months:
                cohort.duration_months = 3
                changed_fields.append("duration_months")
            if not cohort.hours_per_week:
                cohort.hours_per_week = 4
                changed_fields.append("hours_per_week")
            if cohort.group_size is None:
                cohort.group_size = 12
                changed_fields.append("group_size")
            if cohort.start_date is None:
                cohort.start_date = today + timedelta(days=30)
                changed_fields.append("start_date")
            if cohort.enrollment_deadline is None:
                cohort.enrollment_deadline = cohort.start_date - timedelta(days=7)
                changed_fields.append("enrollment_deadline")
            if changed_fields:
                cohort.save(update_fields=changed_fields)
                stats["cohorts_repaired"] += 1

    def _ensure_demo_cohort(self, course, stats):
        group_format = self._ensure_format(
            course,
            CourseDeliveryFormat.FormatType.GROUP,
            stats,
        )
        today = timezone.localdate()
        _, created = Cohort.objects.get_or_create(
            course=course,
            delivery_format=group_format,
            name="September group",
            defaults={
                "duration_months": 3,
                "hours_per_week": 5,
                "group_size": 12,
                "start_date": today + timedelta(days=30),
                "enrollment_deadline": today + timedelta(days=23),
                "is_enrollment_open": True,
            },
        )
        if created:
            stats["cohorts_created"] += 1

    def _ensure_curriculum(self, course, stats):
        curriculum = (
            (
                "Foundations",
                "Core concepts and a practical framework.",
                (("Orientation and learning plan", 20, True), ("Essential concepts", 35, False)),
            ),
            (
                "Applied Practice",
                "Turn the concepts into repeatable skills.",
                (("Guided practical exercise", 40, False), ("Final applied project", 50, False)),
            ),
        )
        for module_order, (title, description, lessons) in enumerate(curriculum, start=1):
            module, module_created = Module.objects.get_or_create(
                course=course,
                order=module_order,
                defaults={"title": title, "description": description},
            )
            if module_created:
                stats["modules_created"] += 1
            for lesson_order, (lesson_title, duration, is_preview) in enumerate(
                lessons,
                start=1,
            ):
                _, lesson_created = Lesson.objects.get_or_create(
                    module=module,
                    order=lesson_order,
                    defaults={
                        "title": lesson_title,
                        "duration_minutes": duration,
                        "is_preview": is_preview,
                        "is_mandatory": True,
                    },
                )
                if lesson_created:
                    stats["lessons_created"] += 1

    def _assign_image(self, course, image_path):
        with image_path.open("rb") as image_file:
            course.image.save(image_path.name, File(image_file), save=True)

    def _catalog_issues(self):
        errors = []
        warnings = []
        for course in Course.objects.select_related("category", "teacher_profile__user"):
            prefix = f"{course.slug}:"
            if course.category_id is None:
                errors.append(f"{prefix} category is missing")
            if not (course.short_description or "").strip():
                errors.append(f"{prefix} short_description is empty")
            if not (course.full_description or "").strip():
                errors.append(f"{prefix} full_description is empty")
            if course.status == Course.StatusChoices.PUBLISHED and course.published_at is None:
                errors.append(f"{prefix} published_at is missing")
            if course.is_on_sale and not course.discount_percent:
                errors.append(f"{prefix} sale has no discount_percent")
            if course.teacher_profile.user.role != User.RoleChoices.TEACHER:
                errors.append(f"{prefix} owner is not a teacher")
            if course.teacher_profile.user.is_deleted or course.teacher_profile.user.is_blocked:
                errors.append(f"{prefix} teacher is unavailable")

            formats = list(course.delivery_formats.select_related("pricing"))
            format_types = {item.format_type for item in formats}
            if not formats:
                errors.append(f"{prefix} no delivery formats")
            if course.delivery_type not in format_types:
                errors.append(f"{prefix} primary delivery format is missing")
            for delivery_format in formats:
                if not hasattr(delivery_format, "pricing"):
                    errors.append(
                        f"{prefix} {delivery_format.format_type} has no pricing plan"
                    )
            for cohort in course.cohorts.select_related("delivery_format"):
                if (
                    cohort.delivery_format is None
                    or cohort.delivery_format.format_type
                    != CourseDeliveryFormat.FormatType.GROUP
                ):
                    errors.append(f"{prefix} cohort {cohort.pk} is not linked to group format")

            if not course.image:
                warnings.append(f"{prefix} image is missing")
            if course.status == Course.StatusChoices.PUBLISHED and not course.modules.exists():
                warnings.append(f"{prefix} curriculum is empty")

            actual_review_count = Review.objects.filter(course=course).count()
            if course.rating_count != actual_review_count:
                errors.append(
                    f"{prefix} rating_count is {course.rating_count}, "
                    f"but {actual_review_count} active reviews exist"
                )

        for course_slug, review_specs in REVIEW_SPECS.items():
            course = Course.objects.filter(slug=course_slug).first()
            if course is None:
                errors.append(f"{course_slug}: demo review course is missing")
                continue
            expected_emails = {email for email, _, _ in review_specs}
            actual_emails = set(
                Review.objects.filter(
                    course=course,
                    student__email__in=expected_emails,
                ).values_list("student__email", flat=True)
            )
            for email in sorted(expected_emails - actual_emails):
                errors.append(f"{course_slug}: demo review by {email} is missing")
            enrolled_emails = set(
                Enrollment.objects.filter(
                    course=course,
                    student_profile__user__email__in=expected_emails,
                ).values_list("student_profile__user__email", flat=True)
            )
            for email in sorted(expected_emails - enrolled_emails):
                errors.append(f"{course_slug}: reviewer {email} is not enrolled")
        return errors, warnings

    def _report_validation(self):
        errors, warnings = self._catalog_issues()
        for warning in warnings:
            self.stdout.write(self.style.WARNING(f"WARNING: {warning}"))
        if errors:
            raise CommandError(self._format_issues("Catalog check failed", errors))
        self.stdout.write(
            self.style.SUCCESS(
                f"Catalog check passed: {Course.objects.count()} active courses, "
                f"{len(warnings)} warning(s)."
            )
        )

    @staticmethod
    def _format_issues(title, issues):
        return title + ":\n- " + "\n- ".join(issues)

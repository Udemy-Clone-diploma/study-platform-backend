from datetime import datetime, time

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.courses.exceptions import CoursesError
from apps.courses.management.commands.teacher_demo_catalog import (
    COURSES,
    QUIZZES,
    REVISION_COMMENT,
)
from apps.courses.models import (
    Category,
    Cohort,
    Course,
    CourseDeliveryFormat,
    ModerationReview,
    PricingPlan,
)
from apps.courses.services import CourseService, DeliveryFormatService
from apps.curriculum.models import (
    Lesson,
    LessonDocument,
    LessonItem,
    Module,
    Question,
    Test,
)
from apps.schedule.exceptions import TeacherScheduleConflictError
from apps.schedule.models import CohortSchedule, ScheduleSlot
from apps.schedule.services import ScheduleService
from apps.users.models import TeacherProfile, User


class Command(BaseCommand):
    help = "Create or refresh the development-only QA demo catalog for an existing teacher."

    def add_arguments(self, parser):
        parser.add_argument("--teacher-email", required=True)
        parser.add_argument(
            "--force",
            action="store_true",
            help="Allow execution while DEBUG is false (use only in an isolated demo environment).",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            raise CommandError(
                "This demo command is disabled while DEBUG is false. "
                "Use --force only in an isolated demo environment."
            )

        email = options["teacher_email"].strip().lower()
        teacher = self._get_teacher(email)
        category = self._find_category()

        with transaction.atomic():
            self._enrich_teacher_profile(teacher)
            for spec in COURSES:
                self._seed_course(teacher, category, spec)

        self.stdout.write(
            self.style.SUCCESS(f"QA demo catalog ready for {email}: {len(COURSES)} courses.")
        )

    def _get_teacher(self, email):
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist as exc:
            raise CommandError(f"No active user found for {email}.") from exc

        if user.role != User.RoleChoices.TEACHER:
            raise CommandError(f"User {email} is not a teacher.")
        if user.is_blocked:
            raise CommandError(f"Teacher {email} is blocked.")
        profile, _ = TeacherProfile.objects.get_or_create(user=user)
        return profile

    @staticmethod
    def _find_category():
        preferred = ("qa", "software-testing", "testing", "python", "programming")
        for slug in preferred:
            category = Category.objects.filter(slug=slug).first()
            if category:
                return category
        return Category.objects.order_by("name_en").first()

    @staticmethod
    def _enrich_teacher_profile(profile):
        defaults = {
            "specialization": "Quality Assurance and Software Testing",
            "bio": (
                "Experienced QA Engineer and instructor focused on practical manual, API, "
                "database, and test automation skills."
            ),
            "experience": (
                "10 years in software quality assurance using Google tooling, Git, Linux, "
                "Postman, Python, Selenium, and SQL."
            ),
            "years_experience": 10,
            "partnerships_count": 3,
        }
        changed = []
        for field, value in defaults.items():
            if getattr(profile, field) in (None, ""):
                setattr(profile, field, value)
                changed.append(field)
        if changed:
            profile.save(update_fields=changed)

    def _seed_course(self, teacher, category, spec):
        existing = Course.all_objects.filter(slug=spec["slug"]).first()
        if existing and existing.teacher_profile_id != teacher.pk:
            raise CommandError(
                f"Stable demo slug '{spec['slug']}' belongs to another teacher; "
                "refusing to modify that course."
            )

        published_at = self._aware_date(spec["published"]) if spec["published"] else None
        defaults = {
            "teacher_profile": teacher,
            "category": category,
            "title": spec["title"],
            "subtitle": spec["subtitle"],
            "short_description": spec["short_description"],
            "full_description": spec["description"],
            "level": spec["level"],
            "language": Course.LanguageChoices.ENGLISH,
            "mode": (
                Course.ModeChoices.SELF_LEARNING
                if spec["primary"] in {"self_paced", "scheduled"}
                else Course.ModeChoices.WITH_TEACHER
            ),
            "delivery_type": spec["primary"],
            "course_type": Course.CourseTypeChoices.QUALIFICATION,
            "duration_hours": spec["duration"],
            "with_certificate": spec["certificate"],
            "certificate_description": spec["certificate_description"],
            "is_on_sale": spec["sale"],
            "discount_percent": spec["discount"],
            "passing_score": spec["passing_score"],
            "status": spec["status"],
            "published_at": published_at,
            "moderator_comment": (REVISION_COMMENT if spec["status"] == "needs_revision" else ""),
            "is_deleted": False,
        }
        course, _ = Course.all_objects.update_or_create(slug=spec["slug"], defaults=defaults)

        formats = {}
        for format_type, format_spec in spec["formats"].items():
            formats[format_type] = self._seed_format(course, format_type, format_spec)

        for module_order, (module_title, lessons) in enumerate(spec["modules"], start=1):
            module = self._seed_module(course, module_order, module_title)
            for lesson_order, lesson_spec in enumerate(lessons, start=1):
                self._seed_lesson(module, lesson_order, lesson_spec)

        if spec.get("cohort"):
            self._seed_cohort(course, formats["group"], spec["cohort"])
        if spec.get("slots"):
            self._seed_slots(formats["individual"], spec["slots"])
        self._seed_moderation(course, spec["status"])

        created_at = self._aware_date(spec["created"])
        Course.all_objects.filter(pk=course.pk).update(
            created_at=created_at,
            updated_at=max(created_at, published_at or created_at),
        )
        self.stdout.write(f"  {spec['status']:<14} {spec['title']}")

    @staticmethod
    def _seed_format(course, format_type, spec):
        values = {
            "start_type": None,
            "course_start_date": None,
            "access_duration_days": None,
            "start_date": None,
            "unlock_mode": None,
            "max_students": None,
        }
        if format_type == CourseDeliveryFormat.FormatType.SELF_PACED:
            values.update(
                start_type=CourseDeliveryFormat.StartType.MANUAL,
                access_duration_days=spec["access_days"],
            )
        elif format_type in {
            CourseDeliveryFormat.FormatType.SCHEDULED,
            CourseDeliveryFormat.FormatType.GROUP,
        }:
            values.update(start_date=spec["start"], unlock_mode=spec["unlock"])
        else:
            values.update(max_students=spec["max_students"])

        delivery_format, _ = CourseDeliveryFormat.objects.update_or_create(
            course=course,
            format_type=format_type,
            defaults=values,
        )
        installments = spec["installments"]
        pricing = {
            "price": spec["price"],
            "currency": PricingPlan.CurrencyChoices.USD,
            "installment_count": installments[0] if installments else None,
            "installment_amount": installments[1] if installments else None,
        }
        DeliveryFormatService._validate_installment(pricing)
        PricingPlan.objects.update_or_create(delivery_format=delivery_format, defaults=pricing)
        return delivery_format

    @staticmethod
    def _seed_module(course, order, title):
        module, _ = Module.all_objects.update_or_create(
            course=course,
            order=order,
            defaults={
                "title": title,
                "description": f"Practical concepts and guided exercises for {title.lower()}.",
                "is_deleted": False,
            },
        )
        return module

    def _seed_lesson(self, module, order, spec):
        lesson, _ = Lesson.all_objects.update_or_create(
            module=module,
            order=order,
            defaults={
                "title": spec["title"],
                "duration_minutes": spec["duration"],
                "min_score": 70 if spec["quiz"] else None,
                "is_preview": spec["preview"],
                "unlock_after_days": spec["unlock_after_days"],
                "requires_previous": bool(spec["unlock_after_days"]),
                "is_mandatory": True,
                "is_deleted": False,
            },
        )
        body = (
            f"<h2>{spec['title']}</h2><p>In this lesson, students connect core QA principles "
            "to a realistic workplace scenario and finish with a practical verification "
            "task.</p><h3>Learning outcomes</h3><ul><li>Explain the key concepts clearly.</li>"
            "<li>Apply them to a software testing example.</li><li>Document findings in a "
            "professional format.</li></ul>"
        )
        LessonItem.all_objects.update_or_create(
            lesson=lesson,
            order=1,
            defaults={
                "item_type": LessonItem.ItemType.TEXT,
                "body_html": body,
                "is_deleted": False,
            },
        )
        LessonItem.all_objects.update_or_create(
            lesson=lesson,
            order=2,
            defaults={
                "item_type": LessonItem.ItemType.VIDEO,
                "video_url": (
                    "https://storage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"
                ),
                "duration_minutes": max(8, spec["duration"] // 2),
                "original_video_name": f"{spec['title']}.mp4",
                "is_deleted": False,
            },
        )
        if spec["quiz"]:
            self._seed_quiz(module, lesson, spec["quiz"])
        if spec["resource"]:
            self._seed_resource(lesson)

    @staticmethod
    def _seed_quiz(module, lesson, quiz_key):
        test, _ = Test.all_objects.update_or_create(
            module=module,
            order=lesson.order,
            defaults={
                "title": f"{lesson.title} Knowledge Check",
                "description": "Check your understanding before continuing.",
                "passing_score": 70,
                "duration_minutes": 15,
                "allow_retakes": True,
                "max_attempts": 3,
                "is_deleted": False,
            },
        )
        for order, question in enumerate(QUIZZES[quiz_key], start=1):
            question_type, text_value, options, indices, correct_bool, sample = question
            Question.all_objects.update_or_create(
                test=test,
                order=order,
                defaults={
                    "question_type": question_type,
                    "text": text_value,
                    "options": options,
                    "correct_indices": indices,
                    "correct_bool": correct_bool,
                    "sample_answer": sample,
                    "accepted_answers": [sample.lower()] if sample else [],
                    "is_deleted": False,
                },
            )
        LessonItem.all_objects.update_or_create(
            lesson=lesson,
            order=3,
            defaults={
                "item_type": LessonItem.ItemType.TEST,
                "test": test,
                "is_deleted": False,
            },
        )

    @staticmethod
    def _seed_resource(lesson):
        name = f"{lesson.title} - QA worksheet.md"
        if LessonDocument.objects.filter(lesson=lesson, original_name=name).exists():
            return
        content = (
            f"# {lesson.title}\n\n## Objective\n"
            "Apply the lesson to a realistic product scenario.\n\n"
            "## QA checklist\n- Define scope and risks\n- Record test data\n"
            "- Compare expected and actual results\n- Summarize findings\n"
        )
        document = LessonDocument(lesson=lesson, original_name=name)
        document.file.save(name, ContentFile(content.encode("utf-8")), save=True)

    def _seed_cohort(self, course, delivery_format, spec):
        cohort, _ = Cohort.objects.update_or_create(
            course=course,
            name=spec["name"],
            defaults={
                "delivery_format": delivery_format,
                "duration_months": spec["months"],
                "hours_per_week": spec["hours"],
                "group_size": spec["size"],
                "start_date": spec["start"],
                "enrollment_deadline": spec["deadline"],
                "is_enrollment_open": True,
            },
        )
        for day, start, end in spec["schedule"]:
            start_time = time.fromisoformat(start)
            end_time = time.fromisoformat(end)
            if CohortSchedule.objects.filter(
                cohort=cohort,
                day_of_week=day,
                start_time=start_time,
            ).exists():
                continue
            try:
                ScheduleService.create_cohort_schedule(
                    cohort,
                    {
                        "day_of_week": day,
                        "start_time": start_time,
                        "end_time": end_time,
                    },
                )
            except TeacherScheduleConflictError as exc:
                self.stdout.write(self.style.WARNING(f"    schedule skipped: {exc}"))

    def _seed_slots(self, delivery_format, slots):
        for day, start, end in slots:
            start_time = time.fromisoformat(start)
            end_time = time.fromisoformat(end)
            if ScheduleSlot.objects.filter(
                delivery_format=delivery_format,
                day_of_week=day,
                start_time=start_time,
                end_time=end_time,
            ).exists():
                continue
            try:
                ScheduleService.create_schedule_slot(
                    delivery_format,
                    {
                        "day_of_week": day,
                        "start_time": start_time,
                        "end_time": end_time,
                    },
                )
            except TeacherScheduleConflictError as exc:
                self.stdout.write(self.style.WARNING(f"    slot skipped: {exc}"))

    @staticmethod
    def _seed_moderation(course, status):
        if status != Course.StatusChoices.NEEDS_REVISION:
            ModerationReview.objects.filter(course=course).delete()
            return
        try:
            CourseService.reject_course(
                course,
                course.moderator_profile,
                content_action="changes_requested",
                content_comment=REVISION_COMMENT,
                final_action="needs_revision",
                final_comment=REVISION_COMMENT,
            )
        except CoursesError as exc:
            raise CommandError(f"Could not create valid moderation state: {exc}") from exc

    @staticmethod
    def _aware_date(value):
        naive = datetime.combine(value, time(hour=10))
        return timezone.make_aware(naive, timezone.get_current_timezone())

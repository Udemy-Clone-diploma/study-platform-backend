"""Seed the database with rich demo data for local development and demos.

Idempotent: every row is created with get_or_create / update_or_create on a
natural key, or guarded by a seed marker where the model has no natural key, so
running it repeatedly will not duplicate data.

    python manage.py seed
    python manage.py seed --refresh   # also rewrite text on rows seeded earlier

What it covers: users for every role (including a blocked, a soft-deleted, and
an unactivated account), taxonomy, a catalog spanning every course status,
full curricula with course-specific readings and quizzes, enrollments with
backdated progress, auto-graded attempts, notes, completions with certificates,
reviews, wishlists, cohorts and schedules, the whole moderation surface (course
approval and rejection history, submitted pending edits, user reports with
their immutable action chains, teacher applications, reported reviews, chat
rooms with reports and moderation actions), homework with graded submissions,
orders and payments with refunds and teacher payouts, and notifications.

Content lives in `_seed_data/`; this module only decides write order and
idempotency.

Two rules keep this safe to run against a database other people share:

  * It never deletes anything, and never issues a `--flush`-style reset.
  * `--refresh` only rewrites rows this seeder owns, that is accounts in
    DEMO_EMAILS and courses in DEMO_COURSE_SLUGS. Rows created by anyone else
    are never touched.

The denormalized counters (lessons_count, students_count, rating_*,
lessons_completed_count) are intentionally never set here; the app signals
recompute them as rows are created, so the seed stays correct as those rules
change.

All demo users share the password below and are created email-verified, so you
can log in immediately via the auth endpoints.
"""

from datetime import date, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.certificates.models import Certificate
from apps.certificates.serials import generate_unique_serial
from apps.chat.models import (
    ChatModerationAction,
    ChatRoom,
    ChatUserBlock,
    ChatUserRestriction,
    Message,
    MessageReport,
)
from apps.chat.services.chat_service import ChatService
from apps.courses.models import (
    ApprovedCourseRecord,
    Category,
    Cohort,
    CohortMember,
    Course,
    CourseDeliveryFormat,
    CoursePendingEdit,
    ModerationReview,
    PricingPlan,
    RejectedCourseRecord,
    Tag,
)
from apps.courses.services.course_service import CourseService
from apps.courses.services.pending_edit_service import PendingEditService
from apps.curriculum.models import (
    Lesson,
    LessonDocument,
    LessonItem,
    Module,
    Note,
    Question,
    Test,
    TestAttempt,
)
from apps.enrollments.models import CourseCompletion, Enrollment, LessonCompletion
from apps.enrollments.services.certificate_service import CertificateService
from apps.homework.models import (
    HomeworkAssignment,
    HomeworkAssignmentRecipient,
    HomeworkSubmission,
)
from apps.notifications.models import Notification, NotificationPreference
from apps.payments.models import (
    Order,
    OrderItem,
    Payment,
    PaymentAttempt,
    PaymentInstallment,
    PaymentItem,
    Refund,
    TeacherPayoutDestination,
)
from apps.payments.services.teacher_finance import TeacherFinanceService
from apps.reviews.models import Review, ReviewReport
from apps.schedule.models import CohortSchedule, ScheduleSlot
from apps.users.models import (
    AdminNote,
    ModeratorProfile,
    StudentProfile,
    TeacherApplication,
    TeacherProfile,
    User,
    UserReport,
    UserReportAction,
)

from ._seed_data import (
    ADMIN,
    ADMIN_NOTES,
    CHAT_MODERATION,
    CHAT_SCRIPTS,
    COURSE_CONTENT,
    COURSE_MODERATION,
    HOMEWORK_SPECS,
    MODERATORS,
    ORDER_SPECS,
    PAYOUT_SPECS,
    REVIEW_REPORTS,
    STUDENTS,
    TEACHER_APPLICATIONS,
    TEACHERS,
    USER_REPORTS,
)
from ._seed_data.moderation import EXTRA_REVIEWS

DEMO_PASSWORD = "Password123!"

# Rows outside these two sets are never updated, only read. This is what keeps
# --refresh from touching data a teammate created on a shared database.
DEMO_EMAILS = frozenset(
    [ADMIN["email"]] + [person["email"] for person in MODERATORS + TEACHERS + STUDENTS]
)
DEMO_COURSE_SLUGS = frozenset(COURSE_CONTENT)

# Public, stable sample videos so each video lesson plays something different.
SAMPLE_VIDEOS = [
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyrides.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerMeltdowns.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/SubaruOutbackOnStreetAndDirt.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/VolkswagenGTIReview.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/WeAreGoingOnBullrun.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/WhatCarCanYouGetForAGrand.mp4",
]

QUESTION_TYPES = {
    "single_choice": Question.TypeChoices.SINGLE_CHOICE,
    "multiple_choice": Question.TypeChoices.MULTIPLE_CHOICE,
    "true_false": Question.TypeChoices.TRUE_FALSE,
    "short_answer": Question.TypeChoices.SHORT_ANSWER,
}

# Structural course facts. The prose for each slug lives in _seed_data/courses.py;
# `teacher` indexes into TEACHERS, `moderation` is applied by _seed_course_moderation.
COURSE_SPECS = [
    {
        "slug": "backend-engineering-django",
        "teacher": 0,
        "category": "IT",
        "tags": ["python", "django", "beginner-friendly"],
        "course_type": Course.CourseTypeChoices.PROFESSION,
        "level": Course.LevelChoices.BEGINNER,
        "mode": Course.ModeChoices.WITH_TEACHER,
        "delivery_type": Course.DeliveryTypeChoices.GROUP,
        "status": Course.StatusChoices.PUBLISHED,
        "duration_hours": 60,
        "with_certificate": True,
        "is_on_sale": True,
        "discount_percent": 20,
        "created_days_ago": 130,
        "with_meeting": True,
        "formats": [
            {
                "type": "group",
                "price": "149.99",
                "currency": "USD",
                "installment_count": 4,
                "installment_amount": "40.00",
                "unlock_mode": CourseDeliveryFormat.UnlockMode.SEQUENTIAL,
            },
            {"type": "individual", "price": "299.00", "currency": "USD", "max_students": 3},
        ],
        "cohort": {
            "name": "Spring Cohort",
            "months": 3,
            "hours": 5,
            "group_size": 15,
            "days_ahead": 30,
            "format": "group",
            "schedule": [(1, (18, 0), (19, 30)), (3, (18, 0), (19, 30))],
        },
        "slots": [("individual", 0, (10, 0), (11, 0)), ("individual", 2, (14, 0), (15, 0))],
    },
    {
        "slug": "react-from-scratch",
        "teacher": 1,
        "category": "IT",
        "tags": ["react", "beginner-friendly"],
        "course_type": Course.CourseTypeChoices.PROFESSION,
        "level": Course.LevelChoices.INTERMEDIATE,
        "mode": Course.ModeChoices.SELF_LEARNING,
        "delivery_type": Course.DeliveryTypeChoices.SELF_PACED,
        "status": Course.StatusChoices.PUBLISHED,
        "duration_hours": 35,
        "with_certificate": True,
        "created_days_ago": 126,
        "formats": [
            {
                "type": "self_paced",
                "price": "120.00",
                "currency": "EUR",
                "start_type": CourseDeliveryFormat.StartType.MANUAL,
                "access_duration_days": 365,
            },
        ],
    },
    {
        "slug": "ux-design-fundamentals",
        "teacher": 2,
        "category": "Design",
        "tags": ["ux", "beginner-friendly"],
        "course_type": Course.CourseTypeChoices.KNOWLEDGE,
        "level": Course.LevelChoices.BEGINNER,
        "mode": Course.ModeChoices.WITH_TEACHER,
        "delivery_type": Course.DeliveryTypeChoices.GROUP,
        "status": Course.StatusChoices.PUBLISHED,
        "duration_hours": 24,
        "created_days_ago": 60,
        "with_meeting": True,
        "formats": [
            {
                "type": "individual",
                "price": "5000.00",
                "currency": "UAH",
                "installment_count": 5,
                "installment_amount": "1100.00",
                "max_students": 2,
            },
            {
                "type": "group",
                "price": "3000.00",
                "currency": "UAH",
                "unlock_mode": CourseDeliveryFormat.UnlockMode.IMMEDIATE,
            },
        ],
        "cohort": {
            "name": "Evening Group",
            "months": 2,
            "hours": 6,
            "group_size": 12,
            "days_ahead": 21,
            "format": "group",
            "schedule": [(0, (19, 0), (20, 30)), (2, (19, 0), (20, 30))],
        },
    },
    {
        "slug": "data-analysis-bootcamp",
        "teacher": 0,
        "category": "Business",
        "tags": ["python", "analytics"],
        "course_type": Course.CourseTypeChoices.QUALIFICATION,
        "level": Course.LevelChoices.ADVANCED,
        "mode": Course.ModeChoices.WITH_TEACHER,
        "delivery_type": Course.DeliveryTypeChoices.GROUP,
        "status": Course.StatusChoices.PUBLISHED,
        "duration_hours": 50,
        "with_certificate": True,
        "created_days_ago": 50,
        "formats": [
            {
                "type": "group",
                "price": "199.00",
                "currency": "USD",
                "unlock_mode": CourseDeliveryFormat.UnlockMode.DATE_BASED,
            },
        ],
        "cohort": {
            "name": "Weekend Bootcamp",
            "months": 3,
            "hours": 5,
            "group_size": 20,
            "days_ahead": 60,
            "format": "group",
            "schedule": [(5, (11, 0), (13, 0))],
        },
    },
    {
        "slug": "fullstack-javascript",
        "teacher": 1,
        "category": "IT",
        "tags": ["react", "beginner-friendly"],
        "course_type": Course.CourseTypeChoices.PROFESSION,
        "level": Course.LevelChoices.INTERMEDIATE,
        "mode": Course.ModeChoices.SELF_LEARNING,
        "delivery_type": Course.DeliveryTypeChoices.SELF_PACED,
        "status": Course.StatusChoices.PUBLISHED,
        "duration_hours": 45,
        "with_certificate": True,
        "created_days_ago": 40,
        "formats": [
            {
                "type": "self_paced",
                "price": "99.00",
                "currency": "USD",
                "start_type": CourseDeliveryFormat.StartType.MANUAL,
                "access_duration_days": 0,
            },
        ],
    },
    {
        "slug": "advanced-kubernetes",
        "teacher": 1,
        "category": "IT",
        "tags": ["python"],
        "course_type": Course.CourseTypeChoices.PROFESSION,
        "level": Course.LevelChoices.ADVANCED,
        "mode": Course.ModeChoices.SELF_LEARNING,
        "delivery_type": Course.DeliveryTypeChoices.SELF_PACED,
        "status": Course.StatusChoices.DRAFT,
        "duration_hours": 40,
        "created_days_ago": 23,
    },
    {
        # Waiting in the unassigned moderation queue.
        "slug": "marketing-essentials",
        "teacher": 2,
        "category": "Marketing",
        "tags": ["beginner-friendly"],
        "course_type": Course.CourseTypeChoices.KNOWLEDGE,
        "level": Course.LevelChoices.BEGINNER,
        "mode": Course.ModeChoices.WITH_TEACHER,
        "delivery_type": Course.DeliveryTypeChoices.GROUP,
        "status": Course.StatusChoices.REVIEW,
        "duration_hours": 18,
        "created_days_ago": 29,
    },
    {
        # Returned to the teacher; stays assigned to the moderator who returned it.
        "slug": "photography-basics",
        "teacher": 0,
        "category": "Design",
        "tags": ["beginner-friendly"],
        "course_type": Course.CourseTypeChoices.KNOWLEDGE,
        "level": Course.LevelChoices.BEGINNER,
        "mode": Course.ModeChoices.SELF_LEARNING,
        "delivery_type": Course.DeliveryTypeChoices.SELF_PACED,
        "status": Course.StatusChoices.NEEDS_REVISION,
        "duration_hours": 12,
        "created_days_ago": 11,
    },
    {
        "slug": "sql-for-analysts",
        "teacher": 0,
        "category": "Business",
        "tags": ["analytics", "beginner-friendly"],
        "course_type": Course.CourseTypeChoices.KNOWLEDGE,
        "level": Course.LevelChoices.BEGINNER,
        "mode": Course.ModeChoices.SELF_LEARNING,
        "delivery_type": Course.DeliveryTypeChoices.SELF_PACED,
        "status": Course.StatusChoices.REJECTED,
        "duration_hours": 10,
        "created_days_ago": 14,
    },
    {
        # Published once, then taken out of the catalog by an administrator.
        "slug": "intro-to-devops",
        "teacher": 1,
        "category": "IT",
        "tags": ["beginner-friendly"],
        "course_type": Course.CourseTypeChoices.QUALIFICATION,
        "level": Course.LevelChoices.INTERMEDIATE,
        "mode": Course.ModeChoices.SELF_LEARNING,
        "delivery_type": Course.DeliveryTypeChoices.SELF_PACED,
        "status": Course.StatusChoices.HIDDEN,
        "duration_hours": 16,
        "created_days_ago": 40,
        "formats": [{"type": "self_paced", "price": "79.00", "currency": "USD"}],
    },
    {
        "slug": "wordpress-site-building",
        "teacher": 2,
        "category": "Design",
        "tags": ["beginner-friendly"],
        "course_type": Course.CourseTypeChoices.KNOWLEDGE,
        "level": Course.LevelChoices.BEGINNER,
        "mode": Course.ModeChoices.SELF_LEARNING,
        "delivery_type": Course.DeliveryTypeChoices.SELF_PACED,
        "status": Course.StatusChoices.ARCHIVED,
        "duration_hours": 8,
        "created_days_ago": 90,
        "archived": True,
    },
]

# Enrollments: (student index, course slug, lessons completed, format, days of access)
ENROLLMENT_SPECS = [
    (0, "backend-engineering-django", 4, "group", 120),
    (1, "backend-engineering-django", 2, "group", 90),
    (2, "backend-engineering-django", 0, "individual", 20),
    (1, "react-from-scratch", 100, "self_paced", 120),
    (3, "react-from-scratch", 1, "self_paced", 15),
    (9, "react-from-scratch", 3, "self_paced", 45),
    (4, "ux-design-fundamentals", 1, "group", 25),
    (3, "ux-design-fundamentals", 2, "group", 30),
    (2, "data-analysis-bootcamp", 0, "group", 8),
    (3, "data-analysis-bootcamp", 2, "group", 35),
    (9, "data-analysis-bootcamp", 1, "group", 12),
    (5, "fullstack-javascript", 2, "self_paced", 10),
    (8, "fullstack-javascript", 1, "self_paced", 22),
    (6, "react-from-scratch", 1, "self_paced", 30),
    (8, "backend-engineering-django", 1, "group", 38),
]

# Relative ages used to backdate notifications.
AGES = {
    "1 year": timedelta(days=365),
    "7 months": timedelta(days=213),
    "1 month": timedelta(days=30),
    "15 days": timedelta(days=15),
    "1 day": timedelta(days=1),
}


class Command(BaseCommand):
    help = "Seed the database with rich demo data (idempotent, never deletes)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--refresh",
            action="store_true",
            help=(
                "Also rewrite text fields on demo rows an earlier run created. Only rows "
                "this seeder owns are touched: accounts in DEMO_EMAILS and courses in "
                "DEMO_COURSE_SLUGS."
            ),
        )

    def handle(self, *args, **options):
        self.refresh = options["refresh"]
        self._video_i = 0
        self.users = {}
        self.students = []
        self.teachers = []
        self.moderators = []
        self.courses = {}
        self.formats = {}
        self.cohorts = {}
        self.enrollments = {}
        self.chats = {}
        self.chat_messages = {}

        self.stdout.write("Seeding demo data..." + (" (refreshing text)" if self.refresh else ""))

        # One transaction per section rather than one around everything: this runs
        # against a shared remote database, where a single long transaction would
        # hold locks for the whole run.
        sections = [
            ("people", self._seed_people),
            ("taxonomy", self._seed_taxonomy),
            ("catalog", self._seed_catalog),
            ("learning", self._seed_learning),
            ("course moderation", self._seed_course_moderation),
            ("teacher applications", self._seed_teacher_applications),
            ("user reports", self._seed_user_reports),
            ("review moderation", self._seed_review_moderation),
            ("chat", self._seed_chat),
            ("homework", self._seed_homework),
            ("payments", self._seed_payments),
            ("notifications", self._seed_notifications),
        ]
        for label, run in sections:
            with transaction.atomic():
                run()
            self.stdout.write(f"  {label}")

        self._report()

    def _report(self):
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {User.all_objects.count()} users, "
                f"{Course.all_objects.count()} courses, "
                f"{Lesson.objects.count()} lessons, {Test.objects.count()} tests, "
                f"{Enrollment.objects.count()} enrollments, "
                f"{UserReport.objects.count()} user reports, "
                f"{Message.objects.count()} chat messages, "
                f"{Order.objects.count()} orders, {Payment.objects.count()} payments, "
                f"{Notification.objects.count()} notifications. "
                f"Demo password: {DEMO_PASSWORD!r}"
            )
        )

    # People

    def _seed_people(self):
        self.admin = self._user(
            ADMIN["email"],
            User.RoleChoices.ADMINISTRATOR,
            ADMIN["first_name"],
            ADMIN["last_name"],
            is_staff=True,
            is_superuser=True,
            linkedin=ADMIN.get("linkedin", ""),
        )

        for spec in MODERATORS:
            user = self._user(
                spec["email"], User.RoleChoices.MODERATOR, spec["first_name"], spec["last_name"]
            )
            self.moderators.append(
                ModeratorProfile.objects.get_or_create(
                    user=user, defaults={"level": spec["level"]}
                )[0]
            )

        for spec in TEACHERS:
            user = self._user(
                spec["email"],
                User.RoleChoices.TEACHER,
                spec["first_name"],
                spec["last_name"],
                linkedin=spec.get("linkedin", ""),
                instagram=spec.get("instagram", ""),
                status=spec.get("status", "active"),
                is_email_verified=spec.get("is_email_verified", True),
            )
            profile, _ = TeacherProfile.objects.get_or_create(
                user=user,
                defaults={
                    "specialization": spec["specialization"],
                    "experience": spec["experience"],
                    "bio": spec["bio"],
                    "rating": Decimal(spec["rating"]),
                },
            )
            self._sync(
                profile,
                specialization=spec["specialization"],
                experience=spec["experience"],
                bio=spec["bio"],
            )
            self.teachers.append(profile)

        for spec in STUDENTS:
            user = self._user(
                spec["email"],
                User.RoleChoices.STUDENT,
                spec["first_name"],
                spec["last_name"],
                status=spec.get("status", "active"),
                is_blocked=spec.get("is_blocked", False),
                is_deleted=spec.get("is_deleted", False),
            )
            profile, _ = StudentProfile.objects.get_or_create(
                user=user,
                defaults={
                    "learning_goals": spec["learning_goals"],
                    "education_level": spec["education_level"],
                    "date_of_birth": date.fromisoformat(spec["date_of_birth"]),
                },
            )
            self._sync(profile, learning_goals=spec["learning_goals"])
            self.students.append(profile)

        for note in ADMIN_NOTES:
            user = self.users.get(note["user"])
            if user is None:
                continue
            row, _ = AdminNote.objects.get_or_create(
                user=user, defaults={"content": note["content"], "updated_by": self.admin}
            )
            self._backdate(row, "updated_at", self._ago(note["days_ago"]))

    def _user(self, email, role, first, last, **extra):
        # all_objects: the unique email constraint spans soft-deleted rows, so a
        # demo user soft-deleted through the admin panel must be found here, not
        # re-inserted (that would crash the seed with an IntegrityError).
        user, created = User.all_objects.get_or_create(
            email=email,
            defaults={
                "role": role,
                "first_name": first,
                "last_name": last,
                "is_email_verified": True,
                **extra,
            },
        )
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save()
        self._sync(user, first_name=first, last_name=last)
        self.users[email] = user
        return user

    # Taxonomy

    # Translations for the fixed set of demo categories below (apps.courses.migrations
    # .0051_translate_categories backfills the same values for already-seeded databases).
    CATEGORY_TRANSLATIONS = {
        "Design": {
            "name_uk": "Дизайн",
            "name_fr": "Design",
            "name_es": "Diseño",
            "name_de": "Design",
        },
        "Marketing": {
            "name_uk": "Маркетинг",
            "name_fr": "Marketing",
            "name_es": "Marketing",
            "name_de": "Marketing",
        },
        "Languages": {
            "name_uk": "Мови",
            "name_fr": "Langues",
            "name_es": "Idiomas",
            "name_de": "Sprachen",
        },
        "IT": {"name_uk": "ІТ", "name_fr": "Informatique", "name_es": "TI", "name_de": "IT"},
        "Business": {
            "name_uk": "Бізнес",
            "name_fr": "Affaires",
            "name_es": "Negocios",
            "name_de": "Wirtschaft",
        },
    }

    def _seed_taxonomy(self):
        featured_orders = {"IT": 1, "Design": 2, "Marketing": 3}
        self.categories = {
            name: self._category(name, featured_order=featured_orders.get(name))
            for name in ("Design", "Marketing", "Languages", "IT", "Business")
        }
        self.tags = {
            name: Tag.objects.get_or_create(name=name)[0]
            for name in ("python", "django", "react", "ux", "analytics", "beginner-friendly")
        }

    def _category(self, name, featured_order=None):
        translations = self.CATEGORY_TRANSLATIONS.get(name, {})
        cat, created = Category.objects.get_or_create(
            slug=slugify(name),
            defaults={"name_en": name, "featured_order": featured_order, **translations},
        )
        # Only under --refresh: on a shared database the category may predate this
        # seeder, and featured_order decides what the public homepage promotes.
        if not created and self.refresh and cat.featured_order != featured_order:
            cat.featured_order = featured_order
            cat.save(update_fields=["featured_order"])
        return cat

    # Catalog

    def _seed_catalog(self):
        for spec in COURSE_SPECS:
            content = COURSE_CONTENT[spec["slug"]]
            course = self._course(spec, content)
            self.courses[spec["slug"]] = course
            self._curriculum(course, content, with_meeting=spec.get("with_meeting", False))

            for fmt_spec in spec.get("formats", []):
                self.formats[(spec["slug"], fmt_spec["type"])] = self._format(course, fmt_spec)

            cohort_spec = spec.get("cohort")
            if cohort_spec:
                cohort = self._cohort(course, cohort_spec)
                self.cohorts[spec["slug"]] = cohort
                for day, start, end in cohort_spec.get("schedule", []):
                    CohortSchedule.objects.get_or_create(
                        cohort=cohort,
                        day_of_week=day,
                        start_time=time(*start),
                        defaults={"end_time": time(*end)},
                    )

            for fmt_type, day, start, end in spec.get("slots", []):
                ScheduleSlot.objects.get_or_create(
                    delivery_format=self.formats[(spec["slug"], fmt_type)],
                    day_of_week=day,
                    start_time=time(*start),
                    defaults={"end_time": time(*end)},
                )

            if spec.get("archived") and not course.is_deleted:
                CourseService.soft_delete_course(course)

    def _course(self, spec, content):
        status = spec["status"]
        published = status in (Course.StatusChoices.PUBLISHED, Course.StatusChoices.HIDDEN)
        created_at = self._ago(spec["created_days_ago"])
        course, created = Course.all_objects.get_or_create(
            slug=spec["slug"],
            defaults={
                "title": content["title"],
                "subtitle": content["subtitle"],
                "short_description": content["short_description"],
                "full_description": self._full_description(content),
                "teacher_profile": self.teachers[spec["teacher"]],
                "category": self.categories[spec["category"]],
                "course_type": spec["course_type"],
                "level": spec["level"],
                "mode": spec["mode"],
                "delivery_type": spec["delivery_type"],
                "status": status,
                "language": Course.LanguageChoices.ENGLISH,
                "duration_hours": spec["duration_hours"],
                "with_certificate": spec.get("with_certificate", False),
                "certificate_description": content.get("certificate", ""),
                "is_on_sale": spec.get("is_on_sale", False),
                "discount_percent": spec.get("discount_percent"),
                "published_at": created_at + timedelta(days=1) if published else None,
            },
        )
        course.tags.set([self.tags[name] for name in spec.get("tags", [])])
        if created:
            # The moderator dashboard measures review duration from created_at, so a
            # course created seconds before its approval record reports 0.0 hours.
            self._backdate(course, "created_at", created_at)
        self._sync(
            course,
            title=content["title"],
            subtitle=content["subtitle"],
            short_description=content["short_description"],
            full_description=self._full_description(content),
            certificate_description=content.get("certificate", ""),
            mode=spec["mode"],
            delivery_type=spec["delivery_type"],
        )
        return course

    def _full_description(self, content):
        intro = "".join(f"<p>{p}</p>" for p in content["intro"])
        bullets = "".join(f"<li>{b}</li>" for b in content["bullets"])
        requirements = "".join(f"<li>{r}</li>" for r in content["requirements"])
        return (
            f"<h2>About {content['title']}</h2>"
            f"{intro}"
            "<h3>What you will learn</h3>"
            f"<ul>{bullets}</ul>"
            "<h3>Who this course is for</h3>"
            f"<p>{content['audience']}</p>"
            "<h3>Requirements</h3>"
            f"<ul>{requirements}</ul>"
        )

    def _format(self, course, spec):
        fmt_fields = {
            key: value
            for key, value in spec.items()
            if key not in ("type", "price", "currency", "installment_count", "installment_amount")
        }
        fmt, _ = CourseDeliveryFormat.objects.get_or_create(
            course=course, format_type=spec["type"], defaults=fmt_fields
        )
        installment_amount = spec.get("installment_amount")
        PricingPlan.objects.update_or_create(
            delivery_format=fmt,
            defaults={
                "price": Decimal(spec["price"]),
                "currency": spec["currency"],
                "installment_count": spec.get("installment_count"),
                "installment_amount": (Decimal(installment_amount) if installment_amount else None),
            },
        )
        return fmt

    def _cohort(self, course, spec):
        start = (timezone.now() + timedelta(days=spec["days_ahead"])).date()
        # Keyed on the name, not the start date: the date is computed from "today",
        # so re-running on a later day would look like a different cohort and the
        # signal in apps/courses/signals.py would spin up a second group chat too.
        return Cohort.objects.get_or_create(
            course=course,
            name=spec["name"],
            defaults={
                "start_date": start,
                "duration_months": spec["months"],
                "hours_per_week": spec["hours"],
                "group_size": spec.get("group_size"),
                "delivery_format": self.formats.get((course.slug, spec.get("format"))),
                "enrollment_deadline": start - timedelta(days=7),
                "is_enrollment_open": True,
            },
        )[0]

    # Curriculum

    def _curriculum(self, course, content, *, with_meeting=False):
        for module_order, module_spec in enumerate(content["modules"], start=1):
            module, _ = Module.objects.get_or_create(
                course=course,
                order=module_order,
                defaults={
                    "title": module_spec["title"],
                    "description": module_spec["description"],
                },
            )
            self._sync(module, title=module_spec["title"], description=module_spec["description"])

            test = None
            if module_spec.get("test"):
                test = self._test(module, module_spec["test"])

            for lesson_order, lesson_spec in enumerate(module_spec["lessons"], start=1):
                lesson = self._lesson(module, lesson_order, lesson_spec, with_meeting=with_meeting)
                item_order = 0
                if lesson_spec.get("video"):
                    item_order += 1
                    self._video_item(lesson, item_order)
                if lesson_spec.get("reading"):
                    item_order += 1
                    self._reading_item(lesson, item_order, lesson_spec["reading"])
                if lesson_spec.get("test") and test is not None:
                    item_order += 1
                    LessonItem.objects.get_or_create(
                        lesson=lesson,
                        order=item_order,
                        defaults={"item_type": LessonItem.ItemType.TEST, "test": test},
                    )
                if lesson_spec.get("document"):
                    self._document(lesson, lesson_spec["document"])

    def _lesson(self, module, order, spec, *, with_meeting=False):
        lesson, _ = Lesson.objects.get_or_create(
            module=module,
            order=order,
            defaults={
                "title": spec["title"],
                "duration_minutes": 8 + order * 3,
                "is_preview": spec.get("preview", False),
                "meeting_url": "https://meet.example.com/live" if with_meeting else None,
            },
        )
        self._sync(lesson, title=spec["title"])
        return lesson

    def _video_item(self, lesson, order):
        LessonItem.objects.get_or_create(
            lesson=lesson,
            order=order,
            defaults={
                "item_type": LessonItem.ItemType.VIDEO,
                "video_url": self._next_video(),
                "original_video_name": "lecture.mp4",
                "duration_minutes": lesson.duration_minutes or 12,
            },
        )

    def _reading_item(self, lesson, order, reading):
        item, _ = LessonItem.objects.get_or_create(
            lesson=lesson,
            order=order,
            defaults={
                "item_type": LessonItem.ItemType.TEXT,
                "body_html": self._reading_html(reading),
            },
        )
        self._sync(item, body_html=self._reading_html(reading))

    def _reading_html(self, reading):
        paragraphs = "".join(f"<p>{p}</p>" for p in reading["paragraphs"])
        takeaways = "".join(f"<li>{t}</li>" for t in reading["takeaways"])
        return (
            f"<h3>{reading['heading']}</h3>{paragraphs}<h4>Key takeaways</h4><ul>{takeaways}</ul>"
        )

    def _next_video(self):
        url = SAMPLE_VIDEOS[self._video_i % len(SAMPLE_VIDEOS)]
        self._video_i += 1
        return url

    def _document(self, lesson, name):
        # The file column holds a path only; `manage.py seed_media` writes the bytes.
        LessonDocument.objects.get_or_create(
            lesson=lesson,
            original_name=name,
            defaults={"file": f"lessons/documents/{slugify(name)}.pdf"},
        )

    def _test(self, module, spec):
        test, _ = Test.objects.get_or_create(
            module=module,
            order=1,
            defaults={
                "title": spec["title"],
                "description": spec["description"],
                "passing_score": spec["passing_score"],
                "duration_minutes": spec["duration_minutes"],
                "allow_retakes": spec["allow_retakes"],
                "max_attempts": spec["max_attempts"],
            },
        )
        self._sync(test, title=spec["title"], description=spec["description"])
        for order, q in enumerate(spec["questions"], start=1):
            fields = {
                "question_type": QUESTION_TYPES[q["type"]],
                "text": q["text"],
                "options": q.get("options", []),
                "correct_indices": q.get("correct_indices", []),
                "correct_bool": q.get("correct_bool"),
                "sample_answer": q.get("sample_answer", ""),
                "accepted_answers": q.get("accepted_answers", []),
            }
            question, _ = Question.objects.get_or_create(test=test, order=order, defaults=fields)
            self._sync(question, **fields)
        return test

    def _ordered_lessons(self, course):
        return list(Lesson.objects.filter(module__course=course).order_by("module__order", "order"))

    def _ordered_tests(self, course):
        return list(Test.objects.filter(module__course=course).order_by("module__order", "order"))

    # Enrollment, progress, reviews

    REVIEW_SPECS = [
        (
            "backend-engineering-django",
            0,
            5,
            "Best Django course I have taken. The N+1 module alone paid for it.",
            80,
        ),
        (
            "backend-engineering-django",
            1,
            4,
            "Very practical, dense in a good way. Expect to actually build the thing.",
            40,
        ),
        (
            "backend-engineering-django",
            2,
            5,
            "The 1-on-1 sessions were worth the higher tier on their own.",
            10,
        ),
        ("react-from-scratch", 1, 5, "The refactoring sections are what made it click for me.", 25),
        ("react-from-scratch", 3, 4, "Good pace. I would have liked more on testing.", 20),
        (
            "ux-design-fundamentals",
            4,
            4,
            "Loved the hands-on critiques, and the interview module changed how I work.",
            8,
        ),
        (
            "data-analysis-bootcamp",
            3,
            4,
            "Dense but rewarding. The cleaning module is the most useful part.",
            12,
        ),
        (
            "fullstack-javascript",
            5,
            5,
            "Exactly the project I needed to stop copying tutorials.",
            5,
        ),
    ]

    def _seed_learning(self):
        for student_i, slug, completed, fmt_type, granted_days in ENROLLMENT_SPECS:
            enrollment = self._enroll(
                self.students[student_i],
                self.courses[slug],
                completed=completed,
                delivery_format=self.formats.get((slug, fmt_type)),
                granted_days=granted_days,
            )
            self.enrollments[(self.students[student_i].user.email, slug)] = enrollment

        for slug, cohort in self.cohorts.items():
            for (_email, enrolled_slug), enrollment in self.enrollments.items():
                if (
                    enrolled_slug == slug
                    and enrollment.delivery_format_id == cohort.delivery_format_id
                ):
                    CohortMember.objects.get_or_create(cohort=cohort, enrollment=enrollment)

        dj_tests = self._ordered_tests(self.courses["backend-engineering-django"])
        rc_tests = self._ordered_tests(self.courses["react-from-scratch"])
        ux_tests = self._ordered_tests(self.courses["ux-design-fundamentals"])
        da_tests = self._ordered_tests(self.courses["data-analysis-bootcamp"])
        # A fail-then-pass retake, so the attempt history is not uniformly perfect.
        self._attempt(self.students[0], dj_tests[0], correct=0.5, attempt_number=1, days_ago=110)
        self._attempt(self.students[0], dj_tests[0], correct=1.0, attempt_number=2, days_ago=108)
        self._attempt(self.students[0], dj_tests[1], correct=0.75, attempt_number=1, days_ago=70)
        self._attempt(self.students[1], dj_tests[0], correct=1.0, attempt_number=1, days_ago=60)
        self._attempt(self.students[1], rc_tests[0], correct=1.0, attempt_number=1, days_ago=90)
        self._attempt(self.students[1], rc_tests[1], correct=1.0, attempt_number=1, days_ago=60)
        self._attempt(self.students[1], rc_tests[2], correct=0.75, attempt_number=1, days_ago=30)
        self._attempt(self.students[4], ux_tests[0], correct=0.75, attempt_number=1, days_ago=12)
        self._attempt(self.students[3], da_tests[0], correct=0.5, attempt_number=1, days_ago=20)
        self._attempt(self.students[3], da_tests[0], correct=1.0, attempt_number=2, days_ago=18)

        dj_lessons = self._ordered_lessons(self.courses["backend-engineering-django"])
        self._note(
            self.students[0].user,
            dj_lessons[0],
            "Set up the virtualenv before the first exercise.",
            days_ago=100,
        )
        self._note(
            self.students[0].user,
            dj_lessons[1],
            "select_related takes a path, not one call per relation. Revisit before the quiz.",
            days_ago=70,
        )
        self._note(
            self.students[1].user,
            dj_lessons[0],
            "Reminder: migrations are not optional.",
            days_ago=50,
        )

        for slug, student_i, rating, text, days_ago in self.REVIEW_SPECS:
            self._review(
                self.courses[slug], self.students[student_i].user, rating, text, days_ago=days_ago
            )

        self.students[0].wishlisted_courses.add(
            self.courses["react-from-scratch"], self.courses["ux-design-fundamentals"]
        )
        self.students[2].wishlisted_courses.add(
            self.courses["backend-engineering-django"], self.courses["fullstack-javascript"]
        )
        self.students[3].wishlisted_courses.add(self.courses["ux-design-fundamentals"])
        self.students[5].wishlisted_courses.add(self.courses["backend-engineering-django"])

        self._completion(
            self.students[1],
            self.courses["react-from-scratch"],
            final_score=Decimal("92.50"),
            started_days_ago=120,
            completed_days_ago=20,
        )

    def _enroll(self, student, course, *, completed=0, delivery_format=None, granted_days=30):
        granted = self._ago(granted_days)
        enrollment, created = Enrollment.objects.get_or_create(
            student_profile=student,
            course=course,
            defaults={
                "access_status": Enrollment.AccessStatusChoices.ACTIVE,
                "delivery_format": delivery_format,
                "access_granted_at": granted,
            },
        )
        if not created and delivery_format and enrollment.delivery_format_id is None:
            enrollment.delivery_format = delivery_format
            enrollment.save(update_fields=["delivery_format"])

        if completed:
            lessons = self._ordered_lessons(course)[:completed]
            span = timezone.now() - granted
            for i, lesson in enumerate(lessons, start=1):
                lc, _ = LessonCompletion.objects.get_or_create(enrollment=enrollment, lesson=lesson)
                self._backdate(lc, "completed_at", granted + span * i / (len(lessons) + 1))
            if lessons:
                enrollment.last_lesson = lessons[-1]
                enrollment.last_opened_at = self._ago(2)
                enrollment.save(update_fields=["last_lesson", "last_opened_at"])
        return enrollment

    def _attempt(self, student_profile, test, *, correct, attempt_number, days_ago):
        questions = list(test.questions.all().order_by("order"))
        total = len(questions)
        if total == 0:
            return None
        num_correct = round(total * correct)
        answers = [self._answer(q, i < num_correct) for i, q in enumerate(questions)]
        score = round(num_correct / total * 100)
        attempt, created = TestAttempt.objects.get_or_create(
            student_profile=student_profile,
            test=test,
            attempt_number=attempt_number,
            defaults={"score": score, "passed": score >= test.passing_score, "answers": answers},
        )
        if not created and self.refresh:
            # Refreshing rewrites the questions, so stored answers must follow or a
            # demo student's history stops matching the quiz they supposedly took.
            TestAttempt.objects.filter(pk=attempt.pk).update(
                answers=answers, score=score, passed=score >= test.passing_score
            )
        self._backdate(attempt, "submitted_at", self._ago(days_ago))
        return attempt

    def _answer(self, question, correct):
        answer = {"question_id": question.id}
        choice_types = (Question.TypeChoices.SINGLE_CHOICE, Question.TypeChoices.MULTIPLE_CHOICE)
        if question.question_type in choice_types:
            if correct:
                answer["selected_indices"] = list(question.correct_indices)
            else:
                wrong = [
                    i
                    for i in range(len(question.options))
                    if i not in set(question.correct_indices)
                ]
                answer["selected_indices"] = wrong[:1]
        elif question.question_type == Question.TypeChoices.TRUE_FALSE:
            answer["answer_bool"] = question.correct_bool if correct else not question.correct_bool
        elif question.question_type == Question.TypeChoices.SHORT_ANSWER:
            answer["answer_text"] = question.sample_answer if correct else "not sure"
        return answer

    def _note(self, user, lesson, content, days_ago):
        note, _ = Note.objects.get_or_create(
            user=user, lesson=lesson, defaults={"content": content}
        )
        self._backdate(note, "updated_at", self._ago(days_ago))
        return note

    def _review(self, course, user, rating, text, *, days_ago=None, **extra):
        # all_objects: rejecting a reported review sets is_deleted, which hides it
        # from the default manager. get_or_create on `objects` would then try to
        # insert a second review for the same (course, student) pair and crash.
        review, _ = Review.all_objects.get_or_create(
            course=course, student=user, defaults={"rating": rating, "text": text, **extra}
        )
        if days_ago is not None:
            self._backdate(review, "created_at", self._ago(days_ago))
        return review

    def _completion(
        self, student_profile, course, *, final_score, started_days_ago, completed_days_ago
    ):
        completion, _ = CourseCompletion.objects.get_or_create(
            student_profile=student_profile,
            course=course,
            defaults={
                "title": course.title,
                "teacher_name": course.teacher_profile.user.get_full_name(),
                "level": course.level,
                "progress_percent": 100,
                "started_at": self._ago(started_days_ago),
                "final_score": final_score,
            },
        )
        self._backdate(completion, "completed_at", self._ago(completed_days_ago))
        self._render_certificate_files(completion, course)
        self._certificate(completion)
        return completion

    def _render_certificate_files(self, completion, course):
        """Render the real PDF, the way a live completion does. A placeholder
        certificate_url string is not enough: the dashboard and the admin
        download endpoint both serve certificate_file, so a completion without
        one carries a certificate nothing can open."""
        if self._file_exists(completion.certificate_file):
            return
        pdf_bytes, thumbnail_bytes = CertificateService.render_certificate_assets(
            course=course,
            student_name=completion.student_profile.user.get_full_name(),
            course_title=completion.title,
            teacher_name=completion.teacher_name,
            completed_at=completion.completed_at,
        )
        completion.certificate_file.save(
            f"certificate-{completion.id}.pdf", ContentFile(pdf_bytes), save=False
        )
        completion.certificate_thumbnail.save(
            f"certificate-{completion.id}.jpg", ContentFile(thumbnail_bytes), save=False
        )
        completion.certificate_url = completion.certificate_file.url
        completion.save(
            update_fields=["certificate_file", "certificate_thumbnail", "certificate_url"]
        )

    @staticmethod
    def _file_exists(field_file):
        """A truthy FieldFile only means the column holds a name. Seeding a database
        whose files were written against a different storage backend leaves rows
        pointing at bytes that are not there, so check the storage as well."""
        if not field_file:
            return False
        return field_file.storage.exists(field_file.name)

    def _certificate(self, completion):
        """Registry row for the admin Certificates panel. Keyed on the completion so
        re-running the seeder does not mint a second serial."""
        certificate, created = Certificate.objects.get_or_create(
            completion=completion,
            defaults={
                "serial": generate_unique_serial(completion.completed_at.year),
                "student_profile": completion.student_profile,
                "course": completion.course,
                "student_name": completion.student_profile.user.get_full_name(),
                "course_title": completion.title,
                "final_score": completion.final_score,
                "issue_reason": Certificate.IssueReasonChoices.COMPLETION,
                "issued_at": completion.completed_at,
            },
        )
        if created:
            self._backdate(certificate, "created_at", completion.completed_at)
        return certificate

    # Course moderation

    def _seed_course_moderation(self):
        mods = {profile.user.email: profile for profile in self.moderators}

        for spec in COURSE_MODERATION["approvals"]:
            course = self.courses[spec["course"]]
            if ApprovedCourseRecord.objects.filter(course=course).exists():
                continue
            moderator = mods[spec["moderator"]]
            final_status = course.status
            # Replay the real transition rather than writing the record by hand: the
            # service is what decides the snapshot fields and clears the moderator.
            course.status = Course.StatusChoices.REVIEW
            course.moderator_profile = moderator
            course.save(update_fields=["status", "moderator_profile"])
            CourseService.approve_course(course, moderator)
            if final_status != Course.StatusChoices.PUBLISHED:
                course.status = final_status
                course.save(update_fields=["status"])
            record = ApprovedCourseRecord.objects.filter(course=course).latest("id")
            approved_at = self._ago(spec["days_ago"])
            self._backdate(record, "approved_at", approved_at)
            # approve_course stamps published_at with "now"; the catalog orders by it.
            Course.all_objects.filter(pk=course.pk).update(published_at=approved_at)
            course.published_at = approved_at

        by_course = {}
        for spec in COURSE_MODERATION["rejections"]:
            by_course.setdefault(spec["course"], []).append(spec)
        for slug, specs in by_course.items():
            course = self.courses[slug]
            already = RejectedCourseRecord.objects.filter(course=course).count()
            terminal_seen = 0
            for spec in specs:
                if spec["final"] == "rejected":
                    terminal_seen += 1
                    if terminal_seen <= already:
                        continue
                elif ModerationReview.objects.filter(course=course).exists():
                    continue
                self._reject_course(course, mods[spec["moderator"]], spec)

        for spec in COURSE_MODERATION["pending_edits"]:
            self._pending_edit(self.courses[spec["course"]], spec, mods)

    def _reject_course(self, course, moderator, spec):
        if course.status not in (
            Course.StatusChoices.REVIEW,
            Course.StatusChoices.NEEDS_REVISION,
            Course.StatusChoices.REJECTED,
        ):
            course.status = Course.StatusChoices.REVIEW
            course.save(update_fields=["status"])
        course.moderator_profile = moderator
        course.save(update_fields=["moderator_profile"])
        CourseService.reject_course(
            course,
            moderator,
            basics_action="rejected" if spec["basics_comment"] else "",
            basics_comment=spec["basics_comment"],
            content_action="rejected" if spec["content_comment"] else "",
            content_comment=spec["content_comment"],
            final_action=spec["final"],
            final_comment=spec["final_comment"],
        )
        if spec["final"] == "rejected":
            record = RejectedCourseRecord.objects.filter(course=course).latest("id")
            self._backdate(record, "rejected_at", self._ago(spec["days_ago"]))
            if spec.get("restore_after"):
                # The teacher pulled it back into a draft to work on it again.
                CourseService.restore_rejected_course(course)

    def _pending_edit(self, course, spec, mods):
        pending_edit = PendingEditService.get_or_create(course)
        draft = pending_edit.draft_course
        if self.refresh:
            # The draft is cloned once, so a correction made to the live course
            # afterwards has to be carried across by hand or the shadow keeps the
            # old, invalid values.
            Course.all_objects.filter(pk=draft.pk).update(
                mode=course.mode,
                delivery_type=course.delivery_type,
                certificate_description=course.certificate_description,
            )
        if pending_edit.status == CoursePendingEdit.StatusChoices.PENDING:
            return
        for field, value in spec["changes"].items():
            setattr(draft, field, value)
        draft.save(update_fields=list(spec["changes"]))
        PendingEditService.submit(pending_edit)
        if spec["moderator"]:
            pending_edit.moderator_profile = mods[spec["moderator"]]
            pending_edit.save(update_fields=["moderator_profile"])
        self._backdate(pending_edit, "submitted_at", self._ago(spec["submitted_days_ago"]))

    # Teacher applications

    def _seed_teacher_applications(self):
        mods = {profile.user.email: profile for profile in self.moderators}
        for spec in TEACHER_APPLICATIONS:
            application, created = TeacherApplication.objects.get_or_create(
                email=spec["email"],
                defaults={
                    "first_name": spec["first_name"],
                    "last_name": spec["last_name"],
                    "date_of_birth": date.fromisoformat(spec["date_of_birth"]),
                    "phone_number": spec["phone_number"],
                    "bio": spec["bio"],
                    "experience": spec["experience"],
                    "specialization": spec["specialization"],
                    "years_experience": spec["years_experience"],
                    "motivation": spec["motivation"],
                    "instagram": spec.get("instagram", ""),
                    "linkedin": spec.get("linkedin", ""),
                    "behance": spec.get("behance", ""),
                    "status": spec["status"],
                    "moderator_profile": mods.get(spec.get("moderator", "")),
                    "moderator_comment": spec.get("moderator_comment", ""),
                    "decided_at": (
                        self._ago(spec["decided_days_ago"])
                        if spec.get("decided_days_ago")
                        else None
                    ),
                    "created_user": self.users.get(spec.get("creates_user", "")),
                },
            )
            if created:
                application.directions.set(
                    [self.categories[name] for name in spec.get("directions", [])]
                )
            self._backdate(application, "submitted_at", self._ago(spec["submitted_days_ago"]))

    # User reports

    def _seed_user_reports(self):
        mods = {profile.user.email: profile for profile in self.moderators}
        for spec in USER_REPORTS:
            reported = self.users[spec["reported"]]
            reporter = self.users[spec["reporter"]]
            report = UserReport.objects.filter(profile_snapshot__seed_key=spec["key"]).first()
            if report is None:
                report = UserReport.objects.create(
                    reported_user=reported,
                    reporter=reporter,
                    reason=spec["reason"],
                    details=spec["details"],
                    profile_snapshot={
                        "seed_key": spec["key"],
                        "email": reported.email,
                        "full_name": reported.get_full_name(),
                        "role": reported.role,
                    },
                    status=spec["status"],
                    resolution=spec.get("resolution", ""),
                    assigned_moderator=mods.get(spec.get("moderator", "")),
                    assigned_at=self._maybe_ago(spec.get("assigned_days_ago")),
                    escalated_by=self.users.get(spec.get("escalated_by", "")),
                    escalated_at=self._maybe_ago(spec.get("escalated_days_ago")),
                    escalation_note=spec.get("escalation_note", ""),
                    resolved_by=self.users.get(spec.get("resolved_by", "")),
                    resolved_at=self._maybe_ago(spec.get("resolved_days_ago")),
                    resolution_note=spec.get("resolution_note", ""),
                )
                self._backdate(report, "created_at", self._ago(spec["created_days_ago"]))

            # UserReportAction forbids both update and delete, so the chain is built
            # all at once or not at all: a half-written chain can only be repaired
            # with a queryset-level delete.
            if spec["actions"] and not report.actions.exists():
                for action in spec["actions"]:
                    row = UserReportAction.objects.create(
                        report=report,
                        actor=self.users.get(action["actor"]) if action["actor"] else None,
                        actor_role=action["role"],
                        action=action["action"],
                        previous_status=action["previous"],
                        new_status=action["new"],
                        note=action["note"],
                    )
                    self._backdate(row, "created_at", self._ago(action["days_ago"]))

    # Review moderation

    def _seed_review_moderation(self):
        mods = {profile.user.email: profile for profile in self.moderators}

        for spec in EXTRA_REVIEWS:
            review = self._review(
                self.courses[spec["course"]],
                self.users[spec["student"]],
                spec["rating"],
                spec["text"],
                days_ago=spec["days_ago"],
            )
            self._report_review(
                review, spec.get("reporters", []), spec.get("report_reason", ""), spec["days_ago"]
            )
            self._moderate_review(review, spec, mods)

        for spec in REVIEW_REPORTS:
            review = Review.all_objects.filter(
                course=self.courses[spec["course"]], student=self.users[spec["student"]]
            ).first()
            if review is None:
                continue
            self._report_review(review, spec["reporters"], spec["reason"], spec["days_ago"])
            self._moderate_review(review, spec, mods)

    def _report_review(self, review, reporters, reason, days_ago):
        for email in reporters:
            report, created = ReviewReport.objects.get_or_create(
                review=review, reporter=self.users[email], defaults={"reason": reason}
            )
            if created:
                self._backdate(report, "created_at", self._ago(days_ago))

    def _moderate_review(self, review, spec, mods):
        status = spec.get("moderation_status", "")
        if not status:
            return
        review.moderator_profile = mods.get(spec.get("moderator", ""))
        review.moderation_status = status
        review.moderation_assigned_at = self._maybe_ago(spec.get("assigned_days_ago"))
        review.moderated_at = self._maybe_ago(spec.get("moderated_days_ago"))
        review.is_deleted = status == Review.ModerationStatusChoices.REJECTED
        # save() rather than update(): the reviews signals recompute the course
        # rating, and a rejected review must drop out of that average.
        review.save(
            update_fields=[
                "moderator_profile",
                "moderation_status",
                "moderation_assigned_at",
                "moderated_at",
                "is_deleted",
            ]
        )

    # Chat

    def _seed_chat(self):
        for script in CHAT_SCRIPTS:
            chat = self._chat_room(script)
            self.chats[script["key"]] = chat
            messages = list(chat.messages.order_by("created_at", "id"))
            if not messages:
                for sender_email, text, days_ago in script["messages"]:
                    message = ChatService.create_message(chat, self.users[sender_email], text=text)
                    self._backdate(message, "created_at", self._ago(days_ago))
                    messages.append(message)
                self._backdate(chat, "updated_at", self._ago(script["messages"][-1][2]))
            self.chat_messages[script["key"]] = messages

        for spec in CHAT_MODERATION["reports"]:
            message = self.chat_messages[spec["chat"]][spec["message_index"]]
            report, created = MessageReport.objects.get_or_create(
                message=message,
                reporter=self.users[spec["reporter"]],
                defaults={
                    "reason": spec["reason"],
                    "details": spec["details"],
                    "message_text": message.text,
                },
            )
            if created:
                self._backdate(report, "created_at", self._ago(spec["days_ago"]))

        for spec in CHAT_MODERATION["actions"]:
            target = self.users[spec["target"]]
            report = None
            if spec.get("report"):
                message = self.chat_messages[spec["report"]["chat"]][
                    spec["report"]["message_index"]
                ]
                report = MessageReport.objects.filter(message=message).first()
            action, created = ChatModerationAction.objects.get_or_create(
                target_user=target,
                action=spec["action"],
                report=report,
                defaults={"moderator": self.users[spec["moderator"]], "note": spec["note"]},
            )
            if created:
                self._backdate(action, "created_at", self._ago(spec["days_ago"]))

        # Restrictions come after the messages: create_message refuses to write for
        # a restricted user, so restricting first would empty the chat scripts.
        for spec in CHAT_MODERATION["actions"]:
            if spec["action"] not in ("restrict", "restore"):
                continue
            target = self.users[spec["target"]]
            active = spec["target"] in CHAT_MODERATION["active_restrictions"]
            restriction, created = ChatUserRestriction.objects.get_or_create(
                user=target,
                defaults={
                    "restricted_by": self.users[spec["moderator"]],
                    "reason": spec["note"],
                    "is_active": active,
                    "lifted_at": None if active else self._ago(spec["days_ago"]),
                },
            )
            if created:
                self._backdate(restriction, "restricted_at", self._ago(spec["days_ago"]))

        for spec in CHAT_MODERATION["blocks"]:
            ChatUserBlock.objects.get_or_create(
                blocker=self.users[spec["blocker"]], blocked=self.users[spec["blocked"]]
            )

    def _chat_room(self, script):
        if script["type"] == "direct":
            first, second = (self.users[email] for email in script["participants"])
            chat, _ = ChatService.create_direct_chat(first, second)
            return chat
        owner = self.users[script["owner"]]
        others = [
            self.users[email].pk for email in script["participants"] if email != script["owner"]
        ]
        chat = ChatRoom.objects.filter(
            type=ChatRoom.TypeChoices.GROUP, title=script["title"], is_deleted=False
        ).first()
        if chat is None:
            return ChatService.create_group_chat(owner, script["title"], others)
        ChatService.add_participants(chat, others)
        return chat

    # Homework

    def _seed_homework(self):
        for spec in HOMEWORK_SPECS:
            course = self.courses[spec["course"]]
            module = course.modules.order_by("order")[spec["module_index"]]
            teacher_user = course.teacher_profile.user
            assignment, created = HomeworkAssignment.objects.get_or_create(
                course=course,
                title=spec["title"],
                defaults={
                    "module": module,
                    "created_by": teacher_user,
                    "description": spec["description"],
                    "max_score": spec["max_score"],
                    "status": spec["status"],
                    "due_at": self._maybe_ago(spec.get("due_in_days")),
                    "published_at": self._maybe_ago(spec.get("published_days_ago")),
                    "closed_at": self._maybe_ago(spec.get("closed_days_ago")),
                },
            )
            if created and spec.get("published_days_ago"):
                self._backdate(assignment, "created_at", self._ago(spec["published_days_ago"]))

            for email in spec["recipients"]:
                enrollment = self.enrollments.get((email, spec["course"]))
                if enrollment is None:
                    continue
                HomeworkAssignmentRecipient.objects.get_or_create(
                    assignment=assignment, enrollment=enrollment
                )

            for sub in spec["submissions"]:
                enrollment = self.enrollments.get((sub["student"], spec["course"]))
                if enrollment is None:
                    continue
                submission, sub_created = HomeworkSubmission.objects.get_or_create(
                    assignment=assignment,
                    enrollment=enrollment,
                    defaults={
                        "content": sub["content"],
                        "status": sub["status"],
                        "score": sub.get("score"),
                        "feedback": sub.get("feedback", ""),
                        "reviewed_at": self._maybe_ago(sub.get("reviewed_days_ago")),
                    },
                )
                if sub_created:
                    self._backdate(submission, "submitted_at", self._ago(sub["submitted_days_ago"]))

    # Orders, payments, refunds, payouts

    def _seed_payments(self):
        commission = Decimal(str(settings.PLATFORM_COMMISSION_PERCENT))
        for spec in ORDER_SPECS:
            order = self._order(spec)
            installments = self._installments(order, spec)
            payments = [
                self._payment(order, spec, pay, index, commission, installments)
                for index, pay in enumerate(spec["payments"], start=1)
            ]
            if spec.get("refund"):
                self._refund(spec, payments)
        self._payouts()

    def _order(self, spec):
        order = Order.objects.filter(metadata__seed_key=spec["key"]).first()
        if order is not None:
            return order
        user = self.users[spec["student"]]
        course = self.courses[spec["course"]]
        delivery_format = self.formats[(spec["course"], spec["format"])]
        pricing_plan = PricingPlan.objects.filter(delivery_format=delivery_format).first()
        paid_states = (Order.StatusChoices.PAID, Order.StatusChoices.REFUNDED)
        order = Order.objects.create(
            user=user,
            student_profile=user.student_profile,
            total_amount=Decimal(spec["amount"]),
            currency=spec["currency"],
            status=spec["status"],
            payment_type=spec.get("payment_type", Order.PaymentTypeChoices.FULL),
            installments_count=len(spec.get("installments", [])) or 1,
            metadata={"seed_key": spec["key"]},
            completed_at=self._ago(spec["days_ago"]) if spec["status"] in paid_states else None,
        )
        self._backdate(order, "created_at", self._ago(spec["days_ago"]))
        OrderItem.objects.get_or_create(
            order=order,
            course=course,
            defaults={
                "pricing_plan": pricing_plan,
                "cohort": self.cohorts.get(spec["course"]),
                "course_title": course.title,
                "course_slug": course.slug,
                "pricing_plan_kind": delivery_format.format_type,
                "unit_amount": Decimal(spec["amount"]),
                "currency": spec["currency"],
            },
        )
        # Enrollment.order_id is a plain integer column, not a foreign key.
        enrollment = self.enrollments.get((spec["student"], spec["course"]))
        if enrollment is not None and not enrollment.order_id:
            enrollment.order_id = order.pk
            enrollment.save(update_fields=["order_id"])
        return order

    def _installments(self, order, spec):
        installments = {}
        for entry in spec.get("installments", []):
            due = (timezone.now() - timedelta(days=entry["due_days_ago"])).date()
            installment, created = PaymentInstallment.objects.get_or_create(
                order=order,
                installment_number=entry["number"],
                defaults={
                    "amount": Decimal(entry["amount"]),
                    "currency": spec["currency"],
                    "due_date": due,
                    "status": entry["status"],
                    "paid_at": (
                        self._ago(entry["due_days_ago"]) if entry["status"] == "paid" else None
                    ),
                },
            )
            if created:
                self._backdate(installment, "created_at", self._ago(spec["days_ago"]))
            installments[entry["number"]] = installment
        return installments

    def _payment(self, order, spec, pay, index, commission, installments):
        key = f"{spec['key']}-{index}"
        payment = Payment.objects.filter(metadata__seed_key=key).first()
        terminal = pay["status"] in (
            Payment.StatusChoices.SUCCEEDED,
            Payment.StatusChoices.REFUNDED,
            Payment.StatusChoices.FAILED,
            Payment.StatusChoices.CANCELED,
        )
        if payment is None:
            course = self.courses[spec["course"]]
            delivery_format = self.formats[(spec["course"], spec["format"])]
            user = self.users[spec["student"]]
            amount = Decimal(pay["amount"])
            fee = (amount * commission / Decimal("100")).quantize(Decimal("0.01"))
            is_stripe = pay["method"] == Payment.MethodChoices.STRIPE
            payment = Payment.objects.create(
                user=user,
                student_profile=user.student_profile,
                order=order,
                installment=installments.get(pay.get("installment")),
                teacher=course.teacher_profile,
                amount=amount,
                gross_amount=amount,
                platform_fee_amount=fee,
                teacher_amount=amount - fee,
                currency=spec["currency"],
                status=pay["status"],
                payment_method=pay["method"],
                description=f"{course.title} ({delivery_format.get_format_type_display()})",
                metadata={"seed_key": key},
                stripe_payment_intent_id=f"pi_seed_{key}" if is_stripe else "",
                stripe_session_id=f"cs_test_seed_{key}" if is_stripe else "",
                stripe_customer_id=f"cus_seed_{user.pk}" if is_stripe else "",
                stripe_charge_id=(
                    f"ch_seed_{key}"
                    if is_stripe and pay["status"] != Payment.StatusChoices.FAILED
                    else ""
                ),
                processed_at=self._ago(pay["days_ago"]) if terminal else None,
            )
            self._backdate(payment, "created_at", self._ago(pay["days_ago"]))
            PaymentItem.objects.get_or_create(
                payment=payment,
                course=course,
                defaults={
                    "pricing_plan": PricingPlan.objects.filter(
                        delivery_format=delivery_format
                    ).first(),
                    "cohort": self.cohorts.get(spec["course"]),
                    "course_title": course.title,
                    "course_slug": course.slug,
                    "pricing_plan_kind": delivery_format.format_type,
                    "unit_amount": amount,
                    "currency": spec["currency"],
                },
            )
        PaymentAttempt.objects.get_or_create(
            provider=payment.payment_method,
            provider_order_id=f"seed-{key}",
            defaults={
                "payment": payment,
                "provider_payment_id": f"pay_seed_{key}",
                "provider_status": pay["status"],
                "status": pay["status"],
                "error_message": pay.get("error", ""),
                "processed_at": self._ago(pay["days_ago"]) if terminal else None,
            },
        )
        # Stripe payments settle the teacher share through Connect, so only LiqPay
        # ones produce a ledger entry. That is why the method mix is deliberate.
        TeacherFinanceService.ensure_payment_earning(payment)
        return payment

    def _refund(self, spec, payments):
        target = next(
            (
                payment
                for payment in payments
                if payment.status
                in (Payment.StatusChoices.SUCCEEDED, Payment.StatusChoices.REFUNDED)
            ),
            None,
        )
        if target is None:
            return
        entry = spec["refund"]
        key = f"{spec['key']}-refund"
        refund = Refund.objects.filter(metadata__seed_key=key).first()
        if refund is None:
            refund = Refund.objects.create(
                payment=target,
                amount=Decimal(entry["amount"]),
                reason=entry["reason"],
                status=Refund.StatusChoices.SUCCEEDED,
                provider=target.payment_method,
                provider_reference=f"re_seed_{key}",
                provider_status="succeeded",
                stripe_refund_id=(
                    f"re_seed_{key}"
                    if target.payment_method == Payment.MethodChoices.STRIPE
                    else ""
                ),
                metadata={"seed_key": key},
                processed_at=self._ago(entry["days_ago"]),
                created_by=self.admin,
            )
            self._backdate(refund, "created_at", self._ago(entry["days_ago"]))
        TeacherFinanceService.ensure_refund_reservation(refund)
        return refund

    def _payouts(self):
        from apps.payments.services.exceptions import PaymentError

        for spec in PAYOUT_SPECS:
            teacher = self.users[spec["teacher"]].teacher_profile
            destination, _ = TeacherPayoutDestination.objects.get_or_create(
                teacher=teacher,
                receiver_account=spec["destination"]["receiver_account"],
                defaults=spec["destination"],
            )
            for entry in spec["payouts"]:
                try:
                    payout = TeacherFinanceService.reserve_payout(
                        teacher=teacher,
                        destination=destination,
                        amount=Decimal(entry["amount"]),
                        currency=entry["currency"],
                        idempotency_key=entry["key"],
                        created_by=self.admin,
                    )
                    TeacherFinanceService.mark_payout_succeeded(
                        payout,
                        provider_status="success",
                        provider_payment_id=f"po_seed_{entry['key']}",
                    )
                except PaymentError as error:
                    # Balance rules can legitimately refuse a payout (for example when
                    # the LiqPay payments this depends on were reduced by a refund).
                    self.stdout.write(
                        self.style.WARNING(f"    payout {entry['key']} skipped: {error}")
                    )
                    continue
                self._backdate(payout, "created_at", self._ago(entry["days_ago"]))

    # Notifications

    def _seed_notifications(self):
        self._pref(self.students[0].user, {"new_message": {"email": True}})
        self._pref(self.students[1].user, {"homework_graded": {"email": False}})
        self._pref(self.teachers[0].user, {"new_message": {"email": True}})

        django_course = self.courses["backend-engineering-django"]
        ref_lesson = self._ordered_lessons(django_course)[0]
        teacher_user = self.teachers[0].user
        peer_student = self.students[0].user

        student_notifications = [
            {
                "age": "1 year",
                "type": Notification.TypeChoices.SCHEDULE_EVENT,
                "title": "Welcome to the platform",
                "body": "Your orientation session is scheduled. Glad to have you on board.",
                "link": "/student-dashboard/schedule",
                "read": True,
            },
            {
                "age": "7 months",
                "type": Notification.TypeChoices.HOMEWORK_GRADED,
                "title": django_course.title,
                "body": "Your Module 1 assignment was graded: 92 out of 100.",
                "link": f"/learn/{django_course.slug}",
                "read": True,
                "payload": {"course_slug": django_course.slug},
            },
            {
                "age": "1 month",
                "type": Notification.TypeChoices.NEW_LESSON,
                "title": django_course.title,
                "body": f"New lesson published: {ref_lesson.title}",
                "link": f"/learn/{django_course.slug}/{ref_lesson.id}",
                "read": True,
                "payload": {"course_slug": django_course.slug, "lesson_id": ref_lesson.id},
            },
            {
                "age": "15 days",
                "type": Notification.TypeChoices.NEW_MESSAGE,
                "title": teacher_user.get_full_name(),
                "body": "Hi! Let me know if you have questions about the current module.",
                "actor": teacher_user,
                "read": False,
            },
            {
                "age": "1 day",
                "type": Notification.TypeChoices.HOMEWORK_GRADED,
                "title": django_course.title,
                "body": "Great work! Your latest submission scored 88 out of 100.",
                "link": f"/learn/{django_course.slug}",
                "read": False,
                "payload": {"course_slug": django_course.slug},
            },
        ]
        staff_notifications = [
            {
                "age": "7 months",
                "type": Notification.TypeChoices.SCHEDULE_EVENT,
                "title": "Upcoming session",
                "body": "Your next live session is on the calendar.",
                "link": "/teacher-dashboard/schedule",
                "read": True,
            },
            {
                "age": "1 month",
                "type": Notification.TypeChoices.NEW_MESSAGE,
                "title": peer_student.get_full_name(),
                "body": "Thank you for the detailed feedback on my project!",
                "actor": peer_student,
                "read": True,
            },
            {
                "age": "1 day",
                "type": Notification.TypeChoices.NEW_MESSAGE,
                "title": peer_student.get_full_name(),
                "body": "Could you take a look at my latest submission when you have a moment?",
                "actor": peer_student,
                "read": False,
            },
        ]
        moderation_notifications = [
            {
                "age": "15 days",
                "type": Notification.TypeChoices.MODERATION_ACTION,
                "title": "Report escalated to an administrator",
                "body": "A report about a staff account needs an administrator decision.",
                "link": "/admin/reports",
                "read": False,
            },
            {
                "age": "1 day",
                "type": Notification.TypeChoices.MODERATION_ACTION,
                "title": "New course submitted for review",
                "body": "Marketing Essentials is waiting in the unassigned queue.",
                "link": "/moderation/courses",
                "read": False,
            },
        ]
        overdue_notification = [
            {
                "age": "1 day",
                "type": Notification.TypeChoices.PAYMENT_OVERDUE,
                "title": "Installment overdue",
                "body": "Instalment 3 of 4 for Backend Engineering with Django is past its due date.",
                "link": "/student-dashboard/orders",
                "read": False,
            },
        ]

        for student in self.students:
            self._emit_notifications(student.user, student_notifications)
        self._emit_notifications(self.users["tomasz.wisniewski@example.com"], overdue_notification)
        for teacher in self.teachers:
            self._emit_notifications(teacher.user, staff_notifications)
        for moderator in self.moderators:
            self._emit_notifications(moderator.user, staff_notifications)
            self._emit_notifications(moderator.user, moderation_notifications)
        self._emit_notifications(self.admin, staff_notifications)
        self._emit_notifications(self.admin, moderation_notifications)

    def _emit_notifications(self, user, templates):
        for template in templates:
            self._notification(
                user,
                template["type"],
                template["title"],
                template["body"],
                age=AGES[template["age"]],
                seed_key=f"{template['type']}:{template['age']}",
                link_url=template.get("link"),
                actor=template.get("actor"),
                is_read=template.get("read", False),
                payload=template.get("payload"),
            )

    def _notification(
        self,
        recipient,
        ntype,
        title,
        body,
        *,
        age,
        seed_key,
        link_url=None,
        actor=None,
        is_read=False,
        payload=None,
    ):
        if Notification.objects.filter(recipient=recipient, payload__seed_key=seed_key).exists():
            return
        data = dict(payload or {})
        data["seed_key"] = seed_key
        notification = Notification.objects.create(
            recipient=recipient,
            type=ntype,
            title=title,
            body=body,
            link_url=link_url,
            actor=actor,
            is_read=is_read,
            payload=data,
        )
        self._backdate(notification, "created_at", timezone.now() - age)

    def _pref(self, user, overrides):
        NotificationPreference.objects.update_or_create(
            user=user, defaults={"overrides": overrides}
        )

    # Helpers

    @staticmethod
    def _ago(days):
        return timezone.now() - timedelta(days=days)

    def _maybe_ago(self, days):
        return None if days is None else self._ago(days)

    def _sync(self, instance, **fields):
        """Rewrite text on a row an earlier run created.

        get_or_create leaves existing rows untouched, so without this the demo
        content of an already-seeded database never changes. Uses update() rather
        than save(): it skips auto_now (the moderation queues are ordered by
        updated_at, and reshuffling them on every run is confusing) and avoids
        Course.save() recomputing image_hash by reading the file back.
        """
        if not self.refresh or not self._owned(instance):
            return
        manager = getattr(type(instance), "all_objects", None) or type(instance).objects
        manager.filter(pk=instance.pk).update(**fields)
        for key, value in fields.items():
            setattr(instance, key, value)

    @staticmethod
    def _owned(instance):
        """Guard for --refresh: only rows this seeder authored may be rewritten.

        Everything else on a shared database belongs to somebody else. Curriculum
        rows are only ever reached by walking down from a demo course, so they do
        not need their own check.
        """
        if isinstance(instance, User):
            return instance.email in DEMO_EMAILS
        if isinstance(instance, Course):
            return instance.slug in DEMO_COURSE_SLUGS
        if isinstance(instance, (StudentProfile, TeacherProfile, ModeratorProfile)):
            return instance.user.email in DEMO_EMAILS
        return True

    @staticmethod
    def _backdate(instance, field, when):
        """Set an auto_now / auto_now_add timestamp without re-triggering it."""
        manager = getattr(type(instance), "all_objects", None) or type(instance).objects
        manager.filter(pk=instance.pk).update(**{field: when})
        # Keep the in-memory copy in step, so callers that read the field back
        # (the certificate serial year, the rendered PDF date) see the backdate
        # rather than the auto_now_add value from a moment ago.
        setattr(instance, field, when)

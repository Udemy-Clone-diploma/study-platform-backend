"""Seed the database with rich demo data for local development.

Idempotent: every row is created with get_or_create / update_or_create on a
natural key, so running it repeatedly will not duplicate data. Re-run it after a
schema reset (`migrate`) to get a populated dev environment.

    python manage.py seed

What it covers: users for every role with filled-in profiles and social links,
taxonomy, published and in-moderation courses with rich HTML descriptions, full
curricula (rotating sample videos, lorem readings, downloadable documents, and a
test per module), enrollments with backdated progress, auto-graded test attempts
including a fail-then-pass retake, lesson notes, course completions with
certificates, reviews, wishlists, cohorts with weekly schedules and members,
individual 1-on-1 schedule slots, notification preferences, and a year-spanning
set of notifications per user (1 year, 7 months, 1 month, 15 days, and 1 day old).

The denormalized counters (lessons_count, students_count, rating_*,
lessons_completed_count, duration_hours) are intentionally never set here; the
app signals recompute them as rows are created, so the seed stays correct as
those rules change.

All demo users share the password below and are created email-verified, so you
can log in immediately via the auth endpoints.
"""

from datetime import date, time, timedelta
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.certificates.models import Certificate
from apps.certificates.serials import generate_unique_serial
from apps.courses.models import (
    Category,
    Cohort,
    CohortMember,
    Course,
    CourseDeliveryFormat,
    PricingPlan,
    Tag,
)
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
from apps.notifications.models import Notification, NotificationPreference
from apps.reviews.models import Review
from apps.schedule.models import CohortSchedule, ScheduleSlot
from apps.users.models import ModeratorProfile, StudentProfile, TeacherProfile, User

DEMO_PASSWORD = "Password123!"

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

LOREM = [
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, "
    "quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.",
    "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore "
    "eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt "
    "in culpa qui officia deserunt mollit anim id est laborum.",
    "Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium "
    "doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore "
    "veritatis et quasi architecto beatae vitae dicta sunt explicabo.",
    "Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, "
    "sed quia consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt.",
]

MODULE_THEMES = [
    "Getting Started",
    "Core Concepts",
    "Building Real Features",
    "Going to Production",
    "Advanced Topics",
]

# Each set powers one Test. Questions cover all four question types so the
# attempt and grading flow has full coverage. Entries in correct_indices point
# into options; short answers grade against sample_answer plus accepted_answers.
QUESTION_SETS = [
    {
        "title": "Fundamentals check",
        "description": "A quick warm-up to confirm the basics.",
        "passing_score": 60,
        "duration_minutes": 10,
        "allow_retakes": True,
        "max_attempts": 3,
        "questions": [
            {"question_type": Question.TypeChoices.SINGLE_CHOICE,
             "text": "What is 2 + 2?", "options": ["3", "4", "5", "6"],
             "correct_indices": [1]},
            {"question_type": Question.TypeChoices.MULTIPLE_CHOICE,
             "text": "Which of these are prime numbers?",
             "options": ["2", "4", "7", "9"], "correct_indices": [0, 2]},
            {"question_type": Question.TypeChoices.TRUE_FALSE,
             "text": "The sky appears blue on a clear day.", "correct_bool": True},
            {"question_type": Question.TypeChoices.SHORT_ANSWER,
             "text": "What is the capital of France?", "sample_answer": "Paris",
             "accepted_answers": ["Paris, France"]},
        ],
    },
    {
        "title": "Core concepts",
        "description": "Check your understanding of the key ideas.",
        "passing_score": 70,
        "duration_minutes": 15,
        "allow_retakes": True,
        "max_attempts": 3,
        "questions": [
            {"question_type": Question.TypeChoices.SINGLE_CHOICE,
             "text": "Which keyword defines a function in Python?",
             "options": ["func", "def", "function", "fn"], "correct_indices": [1]},
            {"question_type": Question.TypeChoices.MULTIPLE_CHOICE,
             "text": "Which of these are valid HTTP methods?",
             "options": ["GET", "FETCH", "POST", "SEND"], "correct_indices": [0, 2]},
            {"question_type": Question.TypeChoices.TRUE_FALSE,
             "text": "HTML is a programming language.", "correct_bool": False},
            {"question_type": Question.TypeChoices.SHORT_ANSWER,
             "text": "What does API stand for?",
             "sample_answer": "Application Programming Interface",
             "accepted_answers": ["application programming interface"]},
        ],
    },
    {
        "title": "Applied practice",
        "description": "Put the concepts to work on small problems.",
        "passing_score": 75,
        "duration_minutes": 20,
        "allow_retakes": True,
        "max_attempts": 2,
        "questions": [
            {"question_type": Question.TypeChoices.SINGLE_CHOICE,
             "text": "What is the result of 10 % 3?",
             "options": ["0", "1", "3", "10"], "correct_indices": [1]},
            {"question_type": Question.TypeChoices.MULTIPLE_CHOICE,
             "text": "Which of these are relational databases?",
             "options": ["PostgreSQL", "MongoDB", "MySQL", "Redis"],
             "correct_indices": [0, 2]},
            {"question_type": Question.TypeChoices.TRUE_FALSE,
             "text": "A primary key column can contain NULL values.",
             "correct_bool": False},
            {"question_type": Question.TypeChoices.SHORT_ANSWER,
             "text": "Which HTTP status code means 'Not Found'?",
             "sample_answer": "404", "accepted_answers": ["404 not found"]},
        ],
    },
    {
        "title": "Final assessment",
        "description": "The capstone quiz. One shot, make it count.",
        "passing_score": 80,
        "duration_minutes": 30,
        "allow_retakes": False,
        "max_attempts": 1,
        "questions": [
            {"question_type": Question.TypeChoices.SINGLE_CHOICE,
             "text": "Which language is used to style web pages?",
             "options": ["HTML", "CSS", "SQL", "JSON"], "correct_indices": [1]},
            {"question_type": Question.TypeChoices.MULTIPLE_CHOICE,
             "text": "Which of these are version control systems?",
             "options": ["Git", "Docker", "Mercurial", "Nginx"],
             "correct_indices": [0, 2]},
            {"question_type": Question.TypeChoices.TRUE_FALSE,
             "text": "REST APIs are stateless by design.", "correct_bool": True},
            {"question_type": Question.TypeChoices.SHORT_ANSWER,
             "text": "What command initializes a new git repository?",
             "sample_answer": "git init", "accepted_answers": ["init"]},
        ],
    },
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
    help = "Seed the database with rich demo data for local development (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Seeding demo data...")
        self._video_i = 0

        # Users and role-specific profiles
        admin = self._user(
            "admin@example.com", User.RoleChoices.ADMINISTRATOR, "Ada", "Admin",
            is_staff=True, is_superuser=True,
            linkedin="https://linkedin.com/in/ada-admin",
        )

        moderators = [
            self._moderator(
                self._user(f"moderator{i}@example.com",
                           User.RoleChoices.MODERATOR, "Mod", f"Erator{i}"),
                level="senior" if i == 1 else "junior",
            )
            for i in (1, 2)
        ]

        teacher_specs = [
            (1, "Backend Engineering", "10+ years building Django and FastAPI services.",
             Decimal("4.80")),
            (2, "Frontend Development", "Ex-agency lead focused on React and design systems.",
             Decimal("4.60")),
            (3, "Product Design", "Mentored 200+ designers into their first role.",
             Decimal("4.90")),
        ]
        teachers = [
            self._teacher(
                self._user(f"teacher{i}@example.com", User.RoleChoices.TEACHER,
                           "Tessa", f"Teach{i}",
                           linkedin=f"https://linkedin.com/in/teacher{i}",
                           instagram=f"https://instagram.com/teacher{i}"),
                specialization=spec, experience=exp, rating=rating,
            )
            for i, spec, exp, rating in teacher_specs
        ]

        student_profiles = [
            ("Land a first job as a web developer.", "High school", "2001-04-12"),
            ("Switch careers from marketing into UX.", "Bachelor's", "1994-09-30"),
            ("Top up practical skills alongside a CS degree.", "Bachelor's (in progress)", "2003-01-22"),
            ("Fill the gaps left by self-teaching.", "Self-taught", "1998-07-05"),
            ("Move from data analysis into engineering.", "Master's", "1992-11-17"),
            ("Explore design and code as a hobby.", "Some college", "2000-02-28"),
        ]
        students = [
            self._student(
                self._user(f"student{i}@example.com", User.RoleChoices.STUDENT,
                           "Stu", f"Dent{i}"),
                goals=goals, education=edu, dob=date.fromisoformat(dob),
            )
            for i, (goals, edu, dob) in enumerate(student_profiles, start=1)
        ]

        # Taxonomy
        featured_orders = {"IT": 1, "Design": 2, "Marketing": 3}
        cats = {name: self._category(name, featured_order=featured_orders.get(name))
                for name in ("Design", "Marketing", "Languages", "IT", "Business")}
        tags = {name: self._tag(name) for name in
                ("python", "django", "react", "ux", "analytics", "beginner-friendly")}

        # Course 1: Backend Engineering with Django (published, scheduled, with teacher)
        django_course = self._course(
            slug="backend-engineering-django",
            title="Backend Engineering with Django",
            subtitle="From zero to a deployed REST API",
            short_description="Build and ship a production-grade REST API with Django and DRF.",
            bullets=["Model a real domain with the Django ORM",
                     "Design clean REST endpoints with DRF",
                     "Add authentication, permissions, and tests",
                     "Deploy with Docker and CI"],
            teacher=teachers[0], category=cats["IT"],
            tags=[tags["python"], tags["django"], tags["beginner-friendly"]],
            course_type=Course.CourseTypeChoices.PROFESSION,
            level=Course.LevelChoices.BEGINNER,
            mode=Course.ModeChoices.WITH_TEACHER,
            delivery_type=Course.DeliveryTypeChoices.SCHEDULED,
            status=Course.StatusChoices.PUBLISHED,
            language=Course.LanguageChoices.ENGLISH,
            with_certificate=True, is_on_sale=True, duration_hours=60,
        )
        self._curriculum(django_course, modules=3, with_meeting=True)
        grp_django = self._format(
            django_course, "group", Decimal("149.99"), "USD",
            installment_count=4, installment_amount=Decimal("40.00"),
            unlock_mode=CourseDeliveryFormat.UnlockMode.SEQUENTIAL,
        )
        ind_django = self._format(
            django_course, "individual", Decimal("299.00"), "USD", max_students=3,
        )
        django_cohort = self._cohort(
            django_course, name="Spring Cohort", months=3, hours=5,
            group_size=15, days_ahead=30, delivery_format=grp_django,
        )
        self._cohort_schedule(django_cohort, 1, time(18, 0), time(19, 30))
        self._cohort_schedule(django_cohort, 3, time(18, 0), time(19, 30))
        self._schedule_slot(ind_django, 0, time(10, 0), time(11, 0))
        self._schedule_slot(ind_django, 2, time(14, 0), time(15, 0))

        e_s0_django = self._enroll(students[0], django_course, completed=4,
                                   delivery_format=grp_django, granted_days=120)
        e_s1_django = self._enroll(students[1], django_course, completed=2,
                                   delivery_format=grp_django, granted_days=90)
        e_s2_django = self._enroll(students[2], django_course, completed=0,
                                   delivery_format=ind_django, granted_days=20)
        self._cohort_member(django_cohort, e_s0_django)
        self._cohort_member(django_cohort, e_s1_django)
        self._schedule_slot(ind_django, 4, time(16, 0), time(17, 0),
                            booked_by=e_s2_django)

        dj_lessons = self._ordered_lessons(django_course)
        dj_tests = self._ordered_tests(django_course)
        # student0 failed the first quiz, then passed on a retake, then passed module 2.
        self._attempt(students[0], dj_tests[0], correct=0.5, attempt_number=1, days_ago=110)
        self._attempt(students[0], dj_tests[0], correct=1.0, attempt_number=2, days_ago=108)
        self._attempt(students[0], dj_tests[1], correct=0.75, attempt_number=1, days_ago=70)
        self._attempt(students[1], dj_tests[0], correct=1.0, attempt_number=1, days_ago=60)
        self._note(students[0].user, dj_lessons[0],
                   "Set up the virtualenv before the first exercise.", days_ago=100)
        self._note(students[0].user, dj_lessons[1],
                   "The decorator example finally clicked. Revisit before the quiz.", days_ago=70)
        self._note(students[1].user, dj_lessons[0],
                   "Reminder: migrations are not optional.", days_ago=50)
        self._review(django_course, students[0].user, 5,
                     "Best Django course I have taken.", days_ago=80)
        self._review(django_course, students[1].user, 4,
                     "Very practical, dense in a good way.", days_ago=40)
        self._review(django_course, students[2].user, 5,
                     "The 1-on-1 sessions were worth it.", days_ago=10)

        # Course 2: React from Scratch (published, self-paced, EUR)
        react_course = self._course(
            slug="react-from-scratch",
            title="React from Scratch",
            subtitle="Components, hooks, and state done right",
            short_description="Learn modern React: components, hooks, and state management.",
            bullets=["Think in components", "Master hooks and state",
                     "Fetch data and handle effects", "Ship a real single-page app"],
            teacher=teachers[1], category=cats["IT"],
            tags=[tags["react"], tags["beginner-friendly"]],
            course_type=Course.CourseTypeChoices.PROFESSION,
            level=Course.LevelChoices.INTERMEDIATE,
            mode=Course.ModeChoices.SELF_LEARNING,
            delivery_type=Course.DeliveryTypeChoices.SELF_PACED,
            status=Course.StatusChoices.PUBLISHED,
            language=Course.LanguageChoices.ENGLISH,
            with_certificate=True, duration_hours=35,
        )
        self._curriculum(react_course, modules=3)
        sp_react = self._format(
            react_course, "self_paced", Decimal("120.00"), "EUR",
            start_type=CourseDeliveryFormat.StartType.MANUAL, access_duration_days=365,
        )
        self._enroll(students[1], react_course, completed=100,
                     delivery_format=sp_react, granted_days=120)
        self._enroll(students[3], react_course, completed=1,
                     delivery_format=sp_react, granted_days=15)
        rc_tests = self._ordered_tests(react_course)
        self._attempt(students[1], rc_tests[0], correct=1.0, attempt_number=1, days_ago=90)
        self._attempt(students[1], rc_tests[1], correct=1.0, attempt_number=1, days_ago=60)
        self._attempt(students[1], rc_tests[2], correct=0.75, attempt_number=1, days_ago=30)
        self._review(react_course, students[1].user, 5, "Clicked for me finally.", days_ago=25)
        self._completion(students[1], react_course, final_score=Decimal("92.50"),
                         started_days_ago=120, completed_days_ago=20)

        # Course 3: UX Design Fundamentals (published, group, UAH with installments)
        ux_course = self._course(
            slug="ux-design-fundamentals",
            title="UX Design Fundamentals",
            subtitle="Research, wireframes, and usable interfaces",
            short_description="Run research, sketch wireframes, and design usable interfaces.",
            bullets=["Plan and run user research", "Turn insights into wireframes",
                     "Build clickable prototypes", "Test and iterate on designs"],
            teacher=teachers[2], category=cats["Design"],
            tags=[tags["ux"], tags["beginner-friendly"]],
            course_type=Course.CourseTypeChoices.KNOWLEDGE,
            level=Course.LevelChoices.BEGINNER,
            mode=Course.ModeChoices.WITH_TEACHER,
            delivery_type=Course.DeliveryTypeChoices.GROUP,
            status=Course.StatusChoices.PUBLISHED,
            duration_hours=24,
        )
        self._curriculum(ux_course, modules=2, with_meeting=True)
        self._format(
            ux_course, "individual", Decimal("5000.00"), "UAH",
            installment_count=5, installment_amount=Decimal("1100.00"), max_students=2,
        )
        grp_ux = self._format(ux_course, "group", Decimal("3000.00"), "UAH",
                              unlock_mode=CourseDeliveryFormat.UnlockMode.IMMEDIATE)
        ux_cohort = self._cohort(ux_course, name="Evening Group", months=2, hours=6,
                                 group_size=12, days_ahead=21, delivery_format=grp_ux)
        self._cohort_schedule(ux_cohort, 0, time(19, 0), time(20, 30))
        self._cohort_schedule(ux_cohort, 2, time(19, 0), time(20, 30))
        e_s4_ux = self._enroll(students[4], ux_course, completed=1,
                               delivery_format=grp_ux, granted_days=25)
        self._cohort_member(ux_cohort, e_s4_ux)
        ux_tests = self._ordered_tests(ux_course)
        self._attempt(students[4], ux_tests[0], correct=0.75, attempt_number=1, days_ago=12)
        self._review(ux_course, students[4].user, 4, "Loved the hands-on critiques.", days_ago=8)

        # Course 4: Data Analysis Bootcamp (published, scheduled, USD)
        data_course = self._course(
            slug="data-analysis-bootcamp",
            title="Data Analysis Bootcamp",
            subtitle="From spreadsheets to dashboards",
            short_description="Go from spreadsheets to clean dashboards with Python and SQL.",
            bullets=["Clean and shape messy data", "Query with SQL",
                     "Analyze with pandas", "Build dashboards stakeholders trust"],
            teacher=teachers[0], category=cats["IT"],
            tags=[tags["python"], tags["analytics"]],
            course_type=Course.CourseTypeChoices.QUALIFICATION,
            level=Course.LevelChoices.ADVANCED,
            mode=Course.ModeChoices.WITH_TEACHER,
            delivery_type=Course.DeliveryTypeChoices.SCHEDULED,
            status=Course.StatusChoices.PUBLISHED,
            language=Course.LanguageChoices.ENGLISH,
            with_certificate=True, duration_hours=50,
        )
        self._curriculum(data_course, modules=3)
        grp_data = self._format(data_course, "group", Decimal("199.00"), "USD",
                                unlock_mode=CourseDeliveryFormat.UnlockMode.DATE_BASED)
        data_cohort = self._cohort(data_course, name="Weekend Bootcamp", months=3, hours=5,
                                   group_size=20, days_ahead=60, delivery_format=grp_data)
        self._cohort_schedule(data_cohort, 5, time(11, 0), time(13, 0))
        e_s2_data = self._enroll(students[2], data_course, completed=0,
                                 delivery_format=grp_data, granted_days=8)
        e_s3_data = self._enroll(students[3], data_course, completed=2,
                                 delivery_format=grp_data, granted_days=35)
        self._cohort_member(data_cohort, e_s2_data)
        self._cohort_member(data_cohort, e_s3_data)
        data_tests = self._ordered_tests(data_course)
        self._attempt(students[3], data_tests[0], correct=0.5, attempt_number=1, days_ago=20)
        self._attempt(students[3], data_tests[0], correct=1.0, attempt_number=2, days_ago=18)
        self._review(data_course, students[3].user, 4, "Dense but rewarding.", days_ago=12)

        # Course 5: Fullstack JavaScript (published, self-paced, USD)
        fullstack_course = self._course(
            slug="fullstack-javascript",
            title="Fullstack JavaScript",
            subtitle="Node, Express, and a React frontend",
            short_description="Build a fullstack app: a Node and Express API with a React UI.",
            bullets=["Build a REST API with Express", "Persist data in a database",
                     "Connect a React frontend", "Wire up authentication end to end"],
            teacher=teachers[1], category=cats["IT"],
            tags=[tags["react"], tags["beginner-friendly"]],
            course_type=Course.CourseTypeChoices.PROFESSION,
            level=Course.LevelChoices.INTERMEDIATE,
            mode=Course.ModeChoices.SELF_LEARNING,
            delivery_type=Course.DeliveryTypeChoices.SELF_PACED,
            status=Course.StatusChoices.PUBLISHED,
            language=Course.LanguageChoices.ENGLISH,
            with_certificate=True, duration_hours=45,
        )
        self._curriculum(fullstack_course, modules=3)
        sp_fullstack = self._format(
            fullstack_course, "self_paced", Decimal("99.00"), "USD",
            start_type=CourseDeliveryFormat.StartType.MANUAL, access_duration_days=0,
        )
        self._enroll(students[5], fullstack_course, completed=2,
                     delivery_format=sp_fullstack, granted_days=10)
        self._review(fullstack_course, students[5].user, 5,
                     "Exactly the project I needed.", days_ago=5)

        # Non-published states so moderation flows have data to show.
        draft_course = self._course(
            slug="advanced-kubernetes", title="Advanced Kubernetes",
            subtitle="Operators, scaling, and observability",
            short_description="Operate Kubernetes at scale: operators, autoscaling, and observability.",
            bullets=["Write a custom operator", "Autoscale workloads",
                     "Set up observability", "Harden cluster security"],
            teacher=teachers[1], category=cats["IT"], tags=[tags["python"]],
            course_type=Course.CourseTypeChoices.PROFESSION,
            level=Course.LevelChoices.ADVANCED, mode=Course.ModeChoices.SELF_LEARNING,
            delivery_type=Course.DeliveryTypeChoices.SELF_PACED,
            status=Course.StatusChoices.DRAFT, duration_hours=40,
        )
        self._curriculum(draft_course, modules=2)
        self._course(
            slug="marketing-essentials", title="Marketing Essentials",
            subtitle="Channels, funnels, and metrics",
            short_description="Understand channels, funnels, and the metrics that matter.",
            bullets=["Map the marketing funnel", "Pick the right channels",
                     "Measure what matters", "Run your first campaign"],
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
            short_description="Master light, composition, and editing for better photos.",
            bullets=["Control light and exposure", "Compose stronger shots",
                     "Edit with confidence", "Build a small portfolio"],
            teacher=teachers[0], category=cats["Design"], tags=[tags["beginner-friendly"]],
            course_type=Course.CourseTypeChoices.KNOWLEDGE,
            level=Course.LevelChoices.BEGINNER, mode=Course.ModeChoices.SELF_LEARNING,
            delivery_type=Course.DeliveryTypeChoices.SELF_PACED,
            status=Course.StatusChoices.NEEDS_REVISION, duration_hours=12,
            moderator_comment="Please add a syllabus and at least one preview lesson.",
        )

        # Wishlists (plain M2M, distinct from enrollment)
        students[0].wishlisted_courses.add(react_course, ux_course)
        students[2].wishlisted_courses.add(django_course, fullstack_course)
        students[3].wishlisted_courses.add(ux_course)
        students[5].wishlisted_courses.add(django_course)

        # Notification channel preferences (overrides on top of the defaults)
        self._pref(students[0].user, {"new_message": {"email": True}})
        self._pref(students[1].user, {"homework_graded": {"email": False}})
        self._pref(teachers[0].user, {"new_message": {"email": True}})

        # Notifications: same templates for everyone in a role, backdated to the
        # five requested ages so the bell shows a realistic history.
        ref_lesson = dj_lessons[0]
        teacher_user = teachers[0].user
        peer_student = students[0].user
        student_notifications = [
            {"age": "1 year", "type": Notification.TypeChoices.SCHEDULE_EVENT,
             "title": "Welcome to StudyPlatform",
             "body": "Your orientation session is scheduled. Glad to have you on board.",
             "link": "/student-dashboard/schedule", "read": True},
            {"age": "7 months", "type": Notification.TypeChoices.HOMEWORK_GRADED,
             "title": django_course.title,
             "body": "Your Module 1 assignment was graded: 92 out of 100.",
             "link": f"/learn/{django_course.slug}", "read": True,
             "payload": {"course_slug": django_course.slug}},
            {"age": "1 month", "type": Notification.TypeChoices.NEW_LESSON,
             "title": django_course.title,
             "body": f"New lesson published: {ref_lesson.title}",
             "link": f"/learn/{django_course.slug}/{ref_lesson.id}", "read": True,
             "payload": {"course_slug": django_course.slug, "lesson_id": ref_lesson.id}},
            {"age": "15 days", "type": Notification.TypeChoices.NEW_MESSAGE,
             "title": teacher_user.get_full_name(),
             "body": "Hi! Let me know if you have questions about the current module.",
             "actor": teacher_user, "read": False},
            {"age": "1 day", "type": Notification.TypeChoices.HOMEWORK_GRADED,
             "title": django_course.title,
             "body": "Great work! Your latest submission scored 88 out of 100.",
             "link": f"/learn/{django_course.slug}", "read": False,
             "payload": {"course_slug": django_course.slug}},
        ]
        staff_notifications = [
            {"age": "7 months", "type": Notification.TypeChoices.SCHEDULE_EVENT,
             "title": "Upcoming session",
             "body": "Your next live session is on the calendar.",
             "link": "/teacher-dashboard/schedule", "read": True},
            {"age": "1 month", "type": Notification.TypeChoices.NEW_MESSAGE,
             "title": peer_student.get_full_name(),
             "body": "Thank you for the detailed feedback on my project!",
             "actor": peer_student, "read": True},
            {"age": "1 day", "type": Notification.TypeChoices.NEW_MESSAGE,
             "title": peer_student.get_full_name(),
             "body": "Could you take a look at my latest submission when you have a moment?",
             "actor": peer_student, "read": False},
        ]
        for student in students:
            self._emit_notifications(student.user, student_notifications)
        for teacher in teachers:
            self._emit_notifications(teacher.user, staff_notifications)
        for moderator in moderators:
            self._emit_notifications(moderator.user, staff_notifications)
        self._emit_notifications(admin, staff_notifications)

        self.stdout.write(self.style.SUCCESS(
            f"Done. {User.objects.count()} users, {Course.all_objects.count()} courses, "
            f"{Lesson.objects.count()} lessons, {LessonItem.objects.count()} lesson items, "
            f"{Test.objects.count()} tests, {TestAttempt.objects.count()} attempts, "
            f"{Enrollment.objects.count()} enrollments, "
            f"{Notification.objects.count()} notifications. "
            f"Demo password: {DEMO_PASSWORD!r}"
        ))

    # Users

    def _user(self, email, role, first, last, **extra):
        # all_objects: the unique email constraint spans soft-deleted rows, so
        # a demo user soft-deleted via the admin panel must be found here, not
        # re-inserted (that would crash the seed with an IntegrityError).
        user, created = User.all_objects.get_or_create(
            email=email,
            defaults={"role": role, "first_name": first, "last_name": last,
                      "is_email_verified": True, **extra},
        )
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save()
        return user

    def _student(self, user, *, goals="", education="", dob=None):
        return StudentProfile.objects.get_or_create(
            user=user,
            defaults={"learning_goals": goals, "education_level": education,
                      "date_of_birth": dob},
        )[0]

    def _teacher(self, user, *, specialization="", experience="", rating=Decimal("0.00")):
        return TeacherProfile.objects.get_or_create(
            user=user,
            defaults={"specialization": specialization, "experience": experience,
                      "bio": "Practitioner and mentor.", "rating": rating},
        )[0]

    def _moderator(self, user, level="junior"):
        return ModeratorProfile.objects.get_or_create(
            user=user, defaults={"level": level})[0]

    # Taxonomy

    # Translations for the fixed set of demo categories below (apps.courses.migrations
    # .0051_translate_categories backfills the same values for already-seeded databases).
    CATEGORY_TRANSLATIONS = {
        "Design": {"name_uk": "Дизайн", "name_fr": "Design", "name_es": "Diseño", "name_de": "Design"},
        "Marketing": {"name_uk": "Маркетинг", "name_fr": "Marketing", "name_es": "Marketing", "name_de": "Marketing"},
        "Languages": {"name_uk": "Мови", "name_fr": "Langues", "name_es": "Idiomas", "name_de": "Sprachen"},
        "IT": {"name_uk": "ІТ", "name_fr": "Informatique", "name_es": "TI", "name_de": "IT"},
        "Business": {"name_uk": "Бізнес", "name_fr": "Affaires", "name_es": "Negocios", "name_de": "Wirtschaft"},
    }

    def _category(self, name, featured_order=None):
        translations = self.CATEGORY_TRANSLATIONS.get(name, {})
        cat, created = Category.objects.get_or_create(
            slug=slugify(name),
            defaults={"name_en": name, "featured_order": featured_order, **translations})
        if not created and cat.featured_order != featured_order:
            cat.featured_order = featured_order
            cat.save(update_fields=["featured_order"])
        return cat

    def _tag(self, name):
        return Tag.objects.get_or_create(name=name)[0]

    # Courses

    def _course(self, *, slug, title, subtitle, short_description, bullets, teacher,
                category, tags, course_type, level, mode, delivery_type, status,
                duration_hours, language=Course.LanguageChoices.UKRAINIAN,
                with_certificate=False, is_on_sale=False, moderator=None,
                moderator_comment=""):
        published_at = timezone.now() if status == Course.StatusChoices.PUBLISHED else None
        course, _ = Course.all_objects.get_or_create(
            slug=slug,
            defaults={
                "title": title, "subtitle": subtitle,
                "short_description": short_description,
                "full_description": self._full_description(title, bullets),
                "teacher_profile": teacher, "category": category,
                "moderator_profile": moderator,
                "course_type": course_type, "level": level, "mode": mode,
                "delivery_type": delivery_type, "status": status, "language": language,
                "duration_hours": duration_hours,
                "with_certificate": with_certificate, "is_on_sale": is_on_sale,
                "moderator_comment": moderator_comment,
                "published_at": published_at,
            },
        )
        course.tags.set(tags)
        return course

    def _full_description(self, title, bullets):
        items = "".join(f"<li>{b}</li>" for b in bullets)
        return (
            f"<h2>About {title}</h2>"
            f"<p>{LOREM[0]}</p>"
            f"<p>{LOREM[1]}</p>"
            "<h3>What you will learn</h3>"
            f"<ul>{items}</ul>"
            "<h3>Who this course is for</h3>"
            f"<p>{LOREM[2]}</p>"
            "<h3>Requirements</h3>"
            "<ul><li>A computer and an internet connection.</li>"
            "<li>Curiosity and a few hours each week.</li></ul>"
        )

    # Curriculum

    def _curriculum(self, course, *, modules=3, with_meeting=False, with_tests=True):
        """Build a varied curriculum: each module mixes video, reading, document,
        and (by default) a test, with the very first lesson set as a free preview.
        """
        for m in range(1, modules + 1):
            theme = MODULE_THEMES[(m - 1) % len(MODULE_THEMES)]
            module, _ = Module.objects.get_or_create(
                course=course, order=m,
                defaults={"title": f"Module {m}: {theme}",
                          "description": LOREM[m % len(LOREM)]},
            )

            intro = self._lesson(module, 1, f"Introduction to {theme}",
                                 preview=(m == 1), meeting=with_meeting)
            self._video_item(intro, 1)
            self._reading_item(intro, 2, f"Overview of {theme}")

            deep = self._lesson(module, 2, f"{theme} in depth", meeting=with_meeting)
            self._video_item(deep, 1)
            self._reading_item(deep, 2, f"Notes on {theme}")
            if with_tests:
                test = self._test(module, QUESTION_SETS[(m - 1) % len(QUESTION_SETS)])
                self._test_item(deep, 3, test)

            reading = self._lesson(module, 3, f"{theme}: guided reading")
            self._reading_item(reading, 1, f"Deep dive into {theme}")
            self._document(reading, f"{theme} worksheet.pdf")

            if m == 1:
                workshop = self._lesson(module, 4, f"{theme}: hands-on workshop",
                                        meeting=with_meeting)
                self._video_item(workshop, 1)
                self._reading_item(workshop, 2, f"Workshop guide for {theme}")
                self._document(workshop, f"{theme} starter files.zip")

    def _lesson(self, module, order, title, *, preview=False, meeting=False):
        return Lesson.objects.get_or_create(
            module=module, order=order,
            defaults={
                "title": title,
                "duration_minutes": 8 + order * 3,
                "is_preview": preview,
                "meeting_url": "https://meet.example.com/live" if meeting else None,
            },
        )[0]

    def _video_item(self, lesson, order):
        LessonItem.objects.get_or_create(
            lesson=lesson, order=order,
            defaults={
                "item_type": LessonItem.ItemType.VIDEO,
                "video_url": self._next_video(),
                "original_video_name": "lecture.mp4",
                "duration_minutes": lesson.duration_minutes or 12,
            },
        )

    def _reading_item(self, lesson, order, title):
        LessonItem.objects.get_or_create(
            lesson=lesson, order=order,
            defaults={
                "item_type": LessonItem.ItemType.TEXT,
                "body_html": self._reading_html(title),
            },
        )

    def _reading_html(self, title):
        return (
            f"<h3>{title}</h3>"
            f"<p>{LOREM[3]}</p>"
            f"<p>{LOREM[0]}</p>"
            "<h4>Key takeaways</h4>"
            "<ul><li>Grasp the core idea behind this lesson.</li>"
            "<li>Try the inline exercise before moving on.</li>"
            "<li>Skim the summary again right before the quiz.</li></ul>"
        )

    def _test_item(self, lesson, order, test):
        LessonItem.objects.get_or_create(
            lesson=lesson, order=order,
            defaults={"item_type": LessonItem.ItemType.TEST, "test": test},
        )

    def _next_video(self):
        url = SAMPLE_VIDEOS[self._video_i % len(SAMPLE_VIDEOS)]
        self._video_i += 1
        return url

    def _document(self, lesson, name):
        LessonDocument.objects.get_or_create(
            lesson=lesson, original_name=name,
            defaults={"file": f"lessons/documents/{slugify(name)}.pdf"},
        )

    def _test(self, module, qset):
        test, _ = Test.objects.get_or_create(
            module=module, order=1,
            defaults={
                "title": qset["title"], "description": qset["description"],
                "passing_score": qset["passing_score"],
                "duration_minutes": qset["duration_minutes"],
                "allow_retakes": qset["allow_retakes"],
                "max_attempts": qset["max_attempts"],
            },
        )
        for order, question in enumerate(qset["questions"], start=1):
            Question.objects.get_or_create(test=test, order=order, defaults=question)
        return test

    def _ordered_lessons(self, course):
        return list(
            Lesson.objects.filter(module__course=course)
            .order_by("module__order", "order")
        )

    def _ordered_tests(self, course):
        return list(
            Test.objects.filter(module__course=course)
            .order_by("module__order", "order")
        )

    # Pricing, cohorts, schedules

    def _format(self, course, format_type, price, currency, *,
                installment_count=None, installment_amount=None, **fmt_fields):
        fmt, _ = CourseDeliveryFormat.objects.get_or_create(
            course=course, format_type=format_type, defaults=fmt_fields,
        )
        PricingPlan.objects.update_or_create(
            delivery_format=fmt,
            defaults={"price": price, "currency": currency,
                      "installment_count": installment_count,
                      "installment_amount": installment_amount},
        )
        return fmt

    def _cohort(self, course, *, name, months, hours, group_size=None,
                days_ahead=30, delivery_format=None):
        start = (timezone.now() + timedelta(days=days_ahead)).date()
        return Cohort.objects.get_or_create(
            course=course, start_date=start,
            defaults={"name": name, "duration_months": months,
                      "hours_per_week": hours, "group_size": group_size,
                      "delivery_format": delivery_format,
                      "enrollment_deadline": start - timedelta(days=7),
                      "is_enrollment_open": True},
        )[0]

    def _cohort_schedule(self, cohort, day, start, end):
        CohortSchedule.objects.get_or_create(
            cohort=cohort, day_of_week=day, start_time=start,
            defaults={"end_time": end},
        )

    def _cohort_member(self, cohort, enrollment):
        CohortMember.objects.get_or_create(cohort=cohort, enrollment=enrollment)

    def _schedule_slot(self, delivery_format, day, start, end, booked_by=None):
        ScheduleSlot.objects.get_or_create(
            delivery_format=delivery_format, day_of_week=day, start_time=start,
            defaults={"end_time": end, "booked_by": booked_by},
        )

    # Enrollment, progress, attempts

    def _enroll(self, student, course, *, completed=0, delivery_format=None,
                granted_days=30, access_status=Enrollment.AccessStatusChoices.ACTIVE):
        granted = timezone.now() - timedelta(days=granted_days)
        enrollment, created = Enrollment.objects.get_or_create(
            student_profile=student, course=course,
            defaults={"access_status": access_status,
                      "delivery_format": delivery_format,
                      "access_granted_at": granted},
        )
        if not created and delivery_format and enrollment.delivery_format_id is None:
            enrollment.delivery_format = delivery_format
            enrollment.save(update_fields=["delivery_format"])

        if completed:
            lessons = self._ordered_lessons(course)[:completed]
            span = timezone.now() - granted
            for i, lesson in enumerate(lessons, start=1):
                lc, _ = LessonCompletion.objects.get_or_create(
                    enrollment=enrollment, lesson=lesson)
                self._backdate(lc, "completed_at", granted + span * i / (len(lessons) + 1))
            if lessons:
                enrollment.last_lesson = lessons[-1]
                enrollment.last_opened_at = timezone.now() - timedelta(days=2)
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
        attempt, _ = TestAttempt.objects.get_or_create(
            student_profile=student_profile, test=test, attempt_number=attempt_number,
            defaults={"score": score, "passed": score >= test.passing_score,
                      "answers": answers},
        )
        self._backdate(attempt, "submitted_at", timezone.now() - timedelta(days=days_ago))
        return attempt

    def _answer(self, question, correct):
        answer = {"question_id": question.id}
        choice_types = (Question.TypeChoices.SINGLE_CHOICE,
                        Question.TypeChoices.MULTIPLE_CHOICE)
        if question.question_type in choice_types:
            if correct:
                answer["selected_indices"] = list(question.correct_indices)
            else:
                wrong = [i for i in range(len(question.options))
                         if i not in set(question.correct_indices)]
                answer["selected_indices"] = wrong[:1]
        elif question.question_type == Question.TypeChoices.TRUE_FALSE:
            answer["answer_bool"] = (question.correct_bool if correct
                                     else not question.correct_bool)
        elif question.question_type == Question.TypeChoices.SHORT_ANSWER:
            answer["answer_text"] = question.sample_answer if correct else "not sure"
        return answer

    def _note(self, user, lesson, content, days_ago):
        note, _ = Note.objects.get_or_create(
            user=user, lesson=lesson, defaults={"content": content})
        self._backdate(note, "updated_at", timezone.now() - timedelta(days=days_ago))
        return note

    def _review(self, course, user, rating, text, *, days_ago=None):
        review, _ = Review.objects.get_or_create(
            course=course, student=user,
            defaults={"rating": rating, "text": text},
        )
        if days_ago is not None:
            self._backdate(review, "created_at", timezone.now() - timedelta(days=days_ago))
        return review

    def _completion(self, student_profile, course, *, final_score,
                    started_days_ago, completed_days_ago):
        completion, _ = CourseCompletion.objects.get_or_create(
            student_profile=student_profile, course=course,
            defaults={
                "title": course.title,
                "teacher_name": course.teacher_profile.user.get_full_name(),
                "level": course.level,
                "progress_percent": 100,
                "started_at": timezone.now() - timedelta(days=started_days_ago),
                "final_score": final_score,
            },
        )
        self._backdate(completion, "completed_at",
                       timezone.now() - timedelta(days=completed_days_ago))
        self._render_certificate_files(completion, course)
        self._certificate(completion)
        return completion

    def _render_certificate_files(self, completion, course):
        """Render the real PDF, the way a live completion does. A placeholder
        certificate_url string is not enough: the dashboard and the admin
        download endpoint both serve certificate_file, so a completion without
        one carries a certificate nothing can open."""
        if completion.certificate_file:
            return
        pdf_bytes, thumbnail_bytes = CertificateService.render_certificate_assets(
            course=course,
            student_name=completion.student_profile.user.get_full_name(),
            course_title=completion.title,
            teacher_name=completion.teacher_name,
            completed_at=completion.completed_at,
        )
        completion.certificate_file.save(
            f"certificate-{completion.id}.pdf", ContentFile(pdf_bytes), save=False)
        completion.certificate_thumbnail.save(
            f"certificate-{completion.id}.jpg", ContentFile(thumbnail_bytes), save=False)
        completion.certificate_url = completion.certificate_file.url
        completion.save(update_fields=["certificate_file", "certificate_thumbnail",
                                       "certificate_url"])

    def _certificate(self, completion):
        """Registry row for the admin Certificates panel. Keyed on the
        completion so re-running the seeder does not mint a second serial."""
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

    # Notifications

    def _emit_notifications(self, user, templates):
        for t in templates:
            self._notification(
                user, t["type"], t["title"], t["body"],
                age=AGES[t["age"]], seed_key=f'{t["type"]}:{t["age"]}',
                link_url=t.get("link"), actor=t.get("actor"),
                is_read=t.get("read", False), payload=t.get("payload"),
            )

    def _notification(self, recipient, ntype, title, body, *, age, seed_key,
                      link_url=None, actor=None, is_read=False, payload=None):
        if Notification.objects.filter(recipient=recipient,
                                       payload__seed_key=seed_key).exists():
            return
        data = dict(payload or {})
        data["seed_key"] = seed_key
        notification = Notification.objects.create(
            recipient=recipient, type=ntype, title=title, body=body,
            link_url=link_url, actor=actor, is_read=is_read, payload=data,
        )
        self._backdate(notification, "created_at", timezone.now() - age)

    def _pref(self, user, overrides):
        NotificationPreference.objects.update_or_create(
            user=user, defaults={"overrides": overrides})

    # Backdate an auto_now / auto_now_add timestamp without re-triggering it.
    def _backdate(self, instance, field, when):
        instance.__class__.objects.filter(pk=instance.pk).update(**{field: when})
        # Keep the in-memory copy in step, so callers that read the field back
        # (the certificate serial year, the rendered PDF date) see the backdate
        # rather than the auto_now_add value from a moment ago.
        setattr(instance, field, when)

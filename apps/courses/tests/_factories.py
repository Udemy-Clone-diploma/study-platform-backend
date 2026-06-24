from django.utils import timezone

from apps.courses.models import Category, Cohort, Course, CourseDeliveryFormat, PricingPlan
from apps.users.models import TeacherProfile, User


def make_teacher(email="teacher@example.com", first_name="", last_name=""):
    user = User.objects.create_user(
        email=email,
        password="pass12345",
        role="teacher",
        first_name=first_name,
        last_name=last_name,
    )
    profile = TeacherProfile.objects.create(user=user)
    return user, profile


def make_category(name="Development", slug="development", **overrides):
    return Category.objects.create(name=name, slug=slug, **overrides)


COURSE_DEFAULTS = dict(
    short_description="Short",
    full_description="Full",
    level=Course.LevelChoices.BEGINNER,
    language=Course.LanguageChoices.ENGLISH,
    mode=Course.ModeChoices.SELF_LEARNING,
    delivery_type=Course.DeliveryTypeChoices.SELF_PACED,
    course_type=Course.CourseTypeChoices.KNOWLEDGE,
    duration_hours=10,
    lessons_count=0,
    status=Course.StatusChoices.PUBLISHED,
)


def make_course(teacher_profile, *, title="Course", slug="course", **overrides):
    fields = {**COURSE_DEFAULTS, "title": title, "slug": slug}
    fields.update(overrides)
    if (
        fields.get("status") == Course.StatusChoices.PUBLISHED
        and "published_at" not in fields
    ):
        fields["published_at"] = timezone.now()
    return Course.all_objects.create(teacher_profile=teacher_profile, **fields)


def make_pricing_plan(
    course,
    *,
    format_type="group",
    price="100.00",
    currency=PricingPlan.CurrencyChoices.USD,
    **overrides,
):
    fmt, _ = CourseDeliveryFormat.objects.get_or_create(
        course=course, format_type=format_type,
    )
    plan, _ = PricingPlan.objects.update_or_create(
        delivery_format=fmt,
        defaults={"price": price, "currency": currency, **overrides},
    )
    return plan


def make_cohort(
    course,
    *,
    duration_months=3,
    hours_per_week=5,
    **overrides,
):
    return Cohort.objects.create(
        course=course,
        duration_months=duration_months,
        hours_per_week=hours_per_week,
        **overrides,
    )

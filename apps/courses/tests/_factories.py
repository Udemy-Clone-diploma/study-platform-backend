from apps.courses.models import Category, Course
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
    pricing_type=Course.PricingTypeChoices.FREE,
    price=0,
    duration_hours=10,
    lessons_count=0,
)


def make_course(teacher_profile, *, title="Course", slug="course", **overrides):
    fields = {**COURSE_DEFAULTS, "title": title, "slug": slug}
    fields.update(overrides)
    return Course.all_objects.create(teacher_profile=teacher_profile, **fields)

from django.db import transaction
from django.db.models import Min, OuterRef, Q, Subquery
from django.utils import timezone
from django.utils.text import slugify

from apps.courses.constants import (
    DEFAULT_FEATURED_CATEGORIES_LIMIT,
    DEFAULT_NEW_COURSES_LIMIT,
    DEFAULT_POPULAR_COURSES_LIMIT,
)
from apps.courses.exceptions import CoursesError
from apps.courses.models import (
    ApprovedCourseRecord,
    Category,
    Course,
    CoursePendingEdit,
    ModerationReview,
    PricingPlan,
    RejectedCourseRecord,
)
from apps.courses.serializers import (
    CategorySerializer,
    CourseCreateUpdateSerializer,
    CourseDetailSerializer,
    CourseListSerializer,
)
from apps.curriculum.models import Lesson, Module, Question, Test
from apps.enrollments.models import Enrollment
from apps.users.models import User


def _course_snapshot_kwargs(course: Course) -> dict:
    return {
        "course_slug": course.slug,
        "course_title": course.title,
        "course_image_url": course.image.url if course.image else None,
        "course_category": course.category.name if course.category else "",
        "course_level": course.level,
    }


class CourseService:
    @staticmethod
    def annotate_min_price(queryset):
        cheapest_plan = (
            PricingPlan.objects.filter(course=OuterRef("pk"))
            .order_by("price")
            .values("currency")[:1]
        )
        return queryset.annotate(
            min_price=Min("pricing_plans__price"),
            min_currency=Subquery(cheapest_plan),
        )

    @staticmethod
    def validate_course_data(
        data: dict,
        course: Course | None = None,
        partial: bool = False,
        context: dict | None = None,
    ) -> dict:
        serializer = CourseCreateUpdateSerializer(
            course,
            data=data,
            partial=partial,
            context=context or {},
        )
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    @classmethod
    def serialize_course_detail(
        cls,
        course: Course,
        context: dict | None = None,
    ) -> dict:
        annotated = cls.annotate_min_price(
            Course.all_objects.filter(pk=course.pk)
        ).first()
        return CourseDetailSerializer(annotated or course, context=context or {}).data

    @classmethod
    def create_course_from_data(cls, data: dict, context: dict) -> dict:
        validated_data = cls.validate_course_data(data, context=context)
        course = cls.create_course(validated_data, request_user=context["request"].user)
        return cls.serialize_course_detail(course, context=context)

    @classmethod
    def update_course_from_data(
        cls,
        course: Course,
        data: dict,
        context: dict,
        partial: bool = True,
    ) -> dict:
        validated_data = cls.validate_course_data(
            data,
            course=course,
            partial=partial,
            context=context,
        )
        course = cls.update_course(
            course,
            validated_data,
            request_user=context["request"].user,
        )
        return cls.serialize_course_detail(course, context=context)

    @staticmethod
    def _resolve_value(
        validated_data: dict,
        field: str,
        course: Course | None,
        default=None,
    ):
        if field in validated_data:
            return validated_data[field]
        if course is not None:
            return getattr(course, field)
        return default

    @classmethod
    def _build_unique_slug(cls, base_value: str, course: Course | None = None) -> str:
        base_slug = slugify(base_value) or "course"
        candidate = base_slug
        suffix = 2

        queryset = Course.all_objects.all()
        if course is not None:
            queryset = queryset.exclude(pk=course.pk)

        while queryset.filter(slug=candidate).exists():
            candidate = f"{base_slug}-{suffix}"
            suffix += 1

        return candidate

    @classmethod
    def _apply_slug_rules(
        cls,
        validated_data: dict,
        course: Course | None = None,
    ) -> dict:
        title = cls._resolve_value(validated_data, "title", course, "")

        if course is None:
            validated_data["slug"] = cls._build_unique_slug(title, None)
            return validated_data

        title_changed = "title" in validated_data and validated_data["title"] != course.title
        can_regenerate_slug = (
            course.status == Course.StatusChoices.DRAFT and title_changed
        )

        if can_regenerate_slug:
            validated_data["slug"] = cls._build_unique_slug(title, course)

        return validated_data

    @staticmethod
    def _apply_teacher_profile_rules(
        validated_data: dict,
        request_user: User,
        course: Course | None = None,
    ) -> dict:
        if request_user.role == User.RoleChoices.ADMINISTRATOR:
            return validated_data

        if course is None:
            validated_data["teacher_profile"] = request_user.teacher_profile
        else:
            validated_data.pop("teacher_profile", None)

        return validated_data

    @staticmethod
    @transaction.atomic
    def create_course(validated_data: dict, request_user: User) -> Course:
        validated_data = CourseService._apply_teacher_profile_rules(
            dict(validated_data),
            request_user,
        )
        validated_data = CourseService._apply_slug_rules(validated_data)
        tags = validated_data.pop("tags", [])
        course = Course.all_objects.create(**validated_data)
        if tags:
            course.tags.set(tags)
        return course

    @staticmethod
    @transaction.atomic
    def update_course(
        course: Course,
        validated_data: dict,
        request_user: User,
    ) -> Course:
        validated_data = CourseService._apply_teacher_profile_rules(
            dict(validated_data),
            request_user,
            course=course,
        )
        validated_data = CourseService._apply_slug_rules(
            validated_data,
            course=course,
        )
        tags = validated_data.pop("tags", None)

        for attr, value in validated_data.items():
            setattr(course, attr, value)

        course.save()

        if tags is not None:
            course.tags.set(tags)

        return course

    @staticmethod
    @transaction.atomic
    def approve_course(course: Course, moderator_profile) -> Course:
        if course.status != Course.StatusChoices.REVIEW:
            raise CoursesError("Only courses in 'review' status can be approved.")
        course.status = Course.StatusChoices.PUBLISHED
        course.moderator_profile = None
        course.moderator_comment = ""
        if not course.published_at:
            course.published_at = timezone.now()
        course.save(update_fields=["status", "moderator_profile", "moderator_comment", "published_at"])
        ModerationReview.objects.filter(course=course).delete()
        ApprovedCourseRecord.objects.create(
            course=course,
            teacher_profile=course.teacher_profile,
            moderator_profile=moderator_profile,
            **_course_snapshot_kwargs(course),
        )
        return course

    @staticmethod
    @transaction.atomic
    def save_review_draft(
        course: Course,
        moderator_profile,
        basics_field_statuses: dict | None = None,
        basics_action: str = "",
        basics_comment: str = "",
        content_item_statuses: dict | None = None,
        content_action: str = "",
        content_comment: str = "",
        final_action: str = "",
        final_comment: str = "",
    ) -> Course:
        ModerationReview.objects.update_or_create(
            course=course,
            defaults={
                "moderator_profile": moderator_profile,
                "basics_field_statuses": basics_field_statuses or {},
                "basics_action": basics_action,
                "basics_comment": basics_comment,
                "content_item_statuses": content_item_statuses or {},
                "content_action": content_action,
                "content_comment": content_comment,
                "final_action": final_action,
                "final_comment": final_comment,
            },
        )
        return course

    @staticmethod
    @transaction.atomic
    def reject_course(
        course: Course,
        moderator_profile,
        basics_field_statuses: dict | None = None,
        basics_action: str = "",
        basics_comment: str = "",
        content_item_statuses: dict | None = None,
        content_action: str = "",
        content_comment: str = "",
        final_action: str = "",
        final_comment: str = "",
    ) -> Course:
        if course.status not in (
            Course.StatusChoices.REVIEW,
            Course.StatusChoices.NEEDS_REVISION,
            Course.StatusChoices.REJECTED,
        ):
            raise CoursesError("Only courses in 'review', 'needs_revision', or 'rejected' status can be moderated.")
        course.status = Course.StatusChoices.REJECTED if final_action == "rejected" else Course.StatusChoices.NEEDS_REVISION
        course.moderator_profile = None
        course.moderator_comment = final_comment
        course.save(update_fields=["status", "moderator_profile", "moderator_comment"])
        if final_action == "rejected":
            ModerationReview.objects.filter(course=course).delete()
            RejectedCourseRecord.objects.create(
                course=course,
                teacher_profile=course.teacher_profile,
                moderator_profile=moderator_profile,
                **_course_snapshot_kwargs(course),
                basics_field_statuses=basics_field_statuses or {},
                basics_action=basics_action,
                basics_comment=basics_comment,
                content_item_statuses=content_item_statuses or {},
                content_action=content_action,
                content_comment=content_comment,
                final_action=final_action,
                final_comment=final_comment,
            )
        else:
            ModerationReview.objects.update_or_create(
                course=course,
                defaults={
                    "moderator_profile": moderator_profile,
                    "basics_field_statuses": basics_field_statuses or {},
                    "basics_action": basics_action,
                    "basics_comment": basics_comment,
                    "content_item_statuses": content_item_statuses or {},
                    "content_action": content_action,
                    "content_comment": content_comment,
                    "final_action": final_action,
                    "final_comment": final_comment,
                },
            )
        return course

    @staticmethod
    @transaction.atomic
    def restore_rejected_course(course: Course) -> Course:
        if course.status != Course.StatusChoices.REJECTED:
            raise CoursesError("Only rejected courses can be restored to draft.")
        course.status = Course.StatusChoices.DRAFT
        course.moderator_comment = ""
        course.moderator_profile = None
        course.save(update_fields=["status", "moderator_comment", "moderator_profile"])
        return course

    @classmethod
    @transaction.atomic
    def copy_to_draft(cls, course: Course, teacher_profile) -> Course:
        """Deep-copy a rejected course into a new DRAFT, leaving the original intact."""
        new_course = Course.all_objects.create(
            title=course.title,
            slug=cls._build_unique_slug(course.title),
            short_description=course.short_description,
            full_description=course.full_description,
            level=course.level,
            language=course.language,
            mode=course.mode,
            delivery_type=course.delivery_type,
            course_type=course.course_type,
            with_certificate=course.with_certificate,
            is_on_sale=course.is_on_sale,
            status=Course.StatusChoices.DRAFT,
            teacher_profile=teacher_profile,
            category=course.category,
            image=course.image,
        )
        new_course.tags.set(course.tags.all())

        for old_mod in course.modules.order_by("order"):
            new_mod = Module.objects.create(
                course=new_course,
                title=old_mod.title,
                description=old_mod.description,
                order=old_mod.order,
            )
            for old_lesson in old_mod.lessons.order_by("order"):
                Lesson.objects.create(
                    module=new_mod,
                    title=old_lesson.title,
                    content=old_lesson.content,
                    video_url=old_lesson.video_url,
                    original_video_name=old_lesson.original_video_name,
                    duration_minutes=old_lesson.duration_minutes,
                    min_score=old_lesson.min_score,
                    is_preview=old_lesson.is_preview,
                    content_type=old_lesson.content_type,
                    body_html=old_lesson.body_html,
                    order=old_lesson.order,
                )
            for old_test in old_mod.tests.order_by("order"):
                new_test = Test.objects.create(
                    module=new_mod,
                    title=old_test.title,
                    description=old_test.description,
                    passing_score=old_test.passing_score,
                    order=old_test.order,
                )
                for old_q in old_test.questions.order_by("order"):
                    Question.objects.create(
                        test=new_test,
                        question_type=old_q.question_type,
                        text=old_q.text,
                        options=old_q.options,
                        correct_index=old_q.correct_index,
                        correct_bool=old_q.correct_bool,
                        sample_answer=old_q.sample_answer,
                        order=old_q.order,
                    )

        return new_course

    @staticmethod
    def get_rejected_courses_queryset(teacher_profile):
        return CourseService.annotate_min_price(
            Course.objects.filter(
                teacher_profile=teacher_profile,
                status=Course.StatusChoices.REJECTED,
            )
            .select_related("category", "teacher_profile__user")
            .prefetch_related("tags")
            .order_by("-updated_at")
        )

    @classmethod
    def get_rejected_moderation_queryset(cls, moderator_profile):
        return cls.annotate_min_price(
            Course.objects.filter(
                moderator_profile=moderator_profile,
                status=Course.StatusChoices.REJECTED,
            )
            .select_related("category", "teacher_profile__user", "moderation_review")
            .prefetch_related("tags")
            .order_by("-updated_at")
        )

    @staticmethod
    @transaction.atomic
    def soft_delete_course(course: Course) -> None:
        course.is_deleted = True
        course.status = Course.StatusChoices.ARCHIVED
        course.save(update_fields=["is_deleted", "status"])

    @classmethod
    def get_unassigned_moderation_queryset(cls):
        """Courses that need moderation and have no moderator assigned yet"""
        return cls.annotate_min_price(
            Course.objects.filter(
                Q(
                    status=Course.StatusChoices.REVIEW,
                    moderator_profile__isnull=True,
                )
                | Q(
                    status=Course.StatusChoices.PUBLISHED,
                    pending_edit__status=CoursePendingEdit.StatusChoices.PENDING,
                    pending_edit__moderator_profile__isnull=True,
                )
            )
            .select_related("teacher_profile__user", "moderator_profile", "category")
            .prefetch_related("tags")
            .order_by("updated_at")
        )

    @classmethod
    def get_my_moderation_queryset(cls, moderator_profile):
        """All courses assigned to the given moderator"""
        return cls.annotate_min_price(
            Course.objects.filter(
                Q(
                    status__in=[
                        Course.StatusChoices.REVIEW,
                        Course.StatusChoices.NEEDS_REVISION,
                        Course.StatusChoices.REJECTED,
                    ],
                    moderator_profile=moderator_profile,
                )
                | Q(
                    status__in=[Course.StatusChoices.PUBLISHED, Course.StatusChoices.HIDDEN],
                    pending_edit__moderator_profile=moderator_profile,
                )
            )
            .distinct()
            .select_related("teacher_profile__user", "moderator_profile", "category")
            .prefetch_related("tags")
            .order_by("updated_at")
        )

    @staticmethod
    @transaction.atomic
    def assign_moderator_self(course: Course, moderator_profile) -> Course:
        """Assign the given moderator to a course that has no moderator yet.

        Handles two cases:
        - status=review: assigns Course.moderator_profile
        - status=published with pending edit: assigns CoursePendingEdit.moderator_profile
        """
        if moderator_profile is None:
            raise CoursesError("Authenticated user does not have a moderator profile.")

        if course.status == Course.StatusChoices.REVIEW:
            if course.moderator_profile_id is not None:
                raise CoursesError("This course already has a moderator assigned.")
            course.moderator_profile = moderator_profile
            course.save(update_fields=["moderator_profile"])
            return course

        if course.status == Course.StatusChoices.PUBLISHED:
            try:
                pending_edit = course.pending_edit
            except CoursePendingEdit.DoesNotExist:
                raise CoursesError("This published course has no pending edit to assign.")
            if pending_edit.status != CoursePendingEdit.StatusChoices.PENDING:
                raise CoursesError("The pending edit is not submitted for moderation yet.")
            if pending_edit.moderator_profile_id is not None:
                raise CoursesError("This pending edit already has a moderator assigned.")
            pending_edit.moderator_profile = moderator_profile
            pending_edit.save(update_fields=["moderator_profile"])
            return course

        raise CoursesError("Only courses in 'review' or published courses with pending edits can be assigned.")

    @classmethod
    def get_teacher_courses_queryset(cls, teacher_profile):
        return cls.annotate_min_price(
            teacher_profile.courses
            .select_related("teacher_profile__user", "category")
            .prefetch_related("tags")
        )

    @classmethod
    def get_enrolled_courses_queryset(cls, student_profile):
        enrolled_at_sq = Subquery(
            Enrollment.objects.with_active_access()
            .filter(student_profile=student_profile, course=OuterRef("pk"))
            .values("access_granted_at")[:1]
        )
        active_course_ids = (
            Enrollment.objects.with_active_access()
            .filter(student_profile=student_profile)
            .values_list("course_id", flat=True)
        )
        return cls.annotate_min_price(
            Course.objects.filter(pk__in=active_course_ids)
            .select_related("teacher_profile__user", "category")
            .prefetch_related("tags")
            .annotate(enrolled_at=enrolled_at_sq)
        )

    @classmethod
    def get_new_courses(
        cls,
        limit: int = DEFAULT_NEW_COURSES_LIMIT,
        context: dict | None = None,
    ) -> list[dict]:
        courses = cls.annotate_min_price(
            Course.objects.filter(status=Course.StatusChoices.PUBLISHED)
        ).order_by("-published_at")[:limit]
        return CourseListSerializer(courses, many=True, context=context or {}).data

    @classmethod
    def get_popular_courses(
        cls,
        limit: int = DEFAULT_POPULAR_COURSES_LIMIT,
        context: dict | None = None,
    ) -> list[dict]:
        courses = cls.annotate_min_price(
            Course.objects.filter(status=Course.StatusChoices.PUBLISHED)
        ).order_by("-rating_avg")[:limit]
        return CourseListSerializer(courses, many=True, context=context or {}).data

    @staticmethod
    def get_categories(limit: int = DEFAULT_FEATURED_CATEGORIES_LIMIT) -> list[dict]:
        categories = Category.objects.all()[:limit]
        return CategorySerializer(categories, many=True).data

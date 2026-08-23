from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import (
    Case,
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    IntegerField,
    Min,
    OuterRef,
    Prefetch,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.text import slugify

from apps.common.files import duplicate_file_field
from apps.courses.constants import (
    DEFAULT_FEATURED_CATEGORIES_LIMIT,
    DEFAULT_NEW_COURSES_LIMIT,
    DEFAULT_POPULAR_COURSES_LIMIT,
    POPULARITY_WINDOW_DAYS,
)
from apps.courses.exceptions import CoursesError
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
)
from apps.courses.serializers import (
    CourseCreateUpdateSerializer,
    CourseDetailSerializer,
    PublicCategorySerializer,
    PublicCourseListSerializer,
)
from apps.courses.services.category_service import CategoryService
from apps.curriculum.models import Lesson, LessonDocument, LessonItem, Module, Question, Test
from apps.enrollments.models import Enrollment
from apps.users.models import User


def _course_snapshot_kwargs(course: Course) -> dict:
    return {
        "course_slug": course.slug,
        "course_title": course.title,
        "course_image_url": course.image.url if course.image else None,
        "course_category": course.category.name_en if course.category else "",
        "course_level": course.level,
    }


class CourseService:
    @staticmethod
    def annotate_min_price(queryset):
        cheapest_plan = (
            PricingPlan.objects.filter(delivery_format__course=OuterRef("pk"))
            .order_by("price")
            .values("currency")[:1]
        )
        queryset = queryset.annotate(
            original_min_price=Min("delivery_formats__pricing__price"),
            min_currency=Subquery(cheapest_plan),
        )
        # original_min_price above is the raw catalog-cheapest plan price; discounts
        # are a uniform course-level percent, so apply it here rather than per-plan.
        # min_price (the discounted, actually-charged amount) is what price_min/
        # price_max filtering and sorting operate on.
        return queryset.annotate(
            min_price=Case(
                When(
                    is_on_sale=True,
                    discount_percent__isnull=False,
                    then=ExpressionWrapper(
                        F("original_min_price")
                        * (Value(Decimal("100")) - F("discount_percent"))
                        / Value(Decimal("100")),
                        output_field=DecimalField(max_digits=10, decimal_places=2),
                    ),
                ),
                default=F("original_min_price"),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            ),
        )

    @staticmethod
    def annotate_recent_enrollments(queryset):
        """Annotate each course with ``students_enrolled_last_30_days``.

        Counts non-soft-deleted enrollments whose ``access_granted_at`` falls
        inside the rolling popularity window. Subsequent state changes (revoke
        or expire) do not retroactively decrement the count, matching a
        "what started recently" intuition rather than "what is currently held."
        """
        cutoff = timezone.now() - timedelta(days=POPULARITY_WINDOW_DAYS)
        return queryset.annotate(
            students_enrolled_last_30_days=Count(
                "enrollments",
                filter=Q(
                    enrollments__access_granted_at__gte=cutoff,
                    enrollments__is_deleted=False,
                ),
                distinct=True,
            ),
        )

    @staticmethod
    def delivery_formats_prefetch() -> Prefetch:
        """Prefetch for Course.delivery_formats with the active-enrollment and
        completed-enrollment counts pre-annotated (see CourseDeliveryFormatSerializer
        .get_enrolled_count/get_completed_count), without this, retrieving a course
        fires one or two COUNT(*) queries per delivery format."""
        completed_subquery = (
            Enrollment.objects.filter(
                delivery_format=OuterRef("pk"),
                access_status=Enrollment.AccessStatusChoices.ACTIVE,
                student_profile__course_completions__course=OuterRef("course"),
            )
            .order_by()
            .values("delivery_format")
            .annotate(c=Count("id", distinct=True))
            .values("c")
        )
        queryset = CourseDeliveryFormat.objects.select_related("pricing").annotate(
            annotated_enrolled_count=Count(
                "enrollments",
                filter=Q(enrollments__access_status=Enrollment.AccessStatusChoices.ACTIVE),
            ),
            annotated_completed_count=Coalesce(
                Subquery(completed_subquery, output_field=IntegerField()),
                0,
            ),
        )
        return Prefetch("delivery_formats", queryset=queryset)

    @staticmethod
    def public_delivery_formats_prefetch() -> Prefetch:
        queryset = CourseDeliveryFormat.objects.select_related("pricing").annotate(
            annotated_enrolled_count=Count(
                "enrollments",
                filter=Q(
                    enrollments__access_status=Enrollment.AccessStatusChoices.ACTIVE,
                ),
            ),
        )
        return Prefetch("delivery_formats", queryset=queryset)

    @staticmethod
    def cohorts_prefetch() -> Prefetch:
        """Prefetch for Course.cohorts with members' enrollment/student/user chain
        select_related in one join, instead of three queries per cohort member
        (CohortMemberSerializer reads enrollment.student_profile.user.* and
        enrollment.course for the is_completed check)."""
        members_queryset = CohortMember.objects.select_related(
            "enrollment__student_profile__user",
            "enrollment__course",
        )
        return Prefetch(
            "cohorts",
            queryset=Cohort.objects.prefetch_related(
                Prefetch("members", queryset=members_queryset),
            ),
        )

    @staticmethod
    def public_cohorts_prefetch() -> Prefetch:
        return Prefetch(
            "cohorts",
            queryset=Cohort.objects.annotate(
                annotated_members_count=Count("members"),
            ),
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
        annotated = cls.annotate_min_price(Course.all_objects.filter(pk=course.pk)).first()
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
        can_regenerate_slug = course.status == Course.StatusChoices.DRAFT and title_changed

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
        old_status = course.status

        for attr, value in validated_data.items():
            setattr(course, attr, value)

        # Leaving the moderation pipeline back to draft/archived (withdraw, archive)
        # releases whichever moderator was assigned, resubmitting later should land
        # back in the unassigned pool, not stay privately assigned to whoever had it
        # before. (Re-submitting straight from needs_revision keeps the moderator,
        # since continuing with the same reviewer for a resubmission is desired.)
        if course.status != old_status and course.status in (
            Course.StatusChoices.DRAFT,
            Course.StatusChoices.ARCHIVED,
        ):
            course.moderator_profile = None

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
        course.save(
            update_fields=["status", "moderator_profile", "moderator_comment", "published_at"]
        )
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
            raise CoursesError(
                "Only courses in 'review', 'needs_revision', or 'rejected' status can be moderated."
            )
        course.status = (
            Course.StatusChoices.REJECTED
            if final_action == "rejected"
            else Course.StatusChoices.NEEDS_REVISION
        )
        if final_action == "rejected":
            course.moderator_profile = None
        course.moderator_comment = final_comment
        update_fields = ["status", "moderator_comment"]
        if final_action == "rejected":
            update_fields.append("moderator_profile")
        course.save(update_fields=update_fields)
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
            duration_hours=course.duration_hours,
            with_certificate=course.with_certificate,
            certificate_description=course.certificate_description,
            is_on_sale=course.is_on_sale,
            discount_percent=course.discount_percent,
            passing_score=course.passing_score,
            status=Course.StatusChoices.DRAFT,
            teacher_profile=teacher_profile,
            category=course.category,
        )
        if course.image:
            duplicate_file_field(course.image, new_course.image)
            new_course.image_hash = course.image_hash
            new_course.save(update_fields=["image", "image_hash"])
        new_course.tags.set(course.tags.all())

        # First pass: copy modules and their tests, recording old->new test ids so
        # TEST-type lesson items can be remapped to the freshly copied tests.
        module_map: dict[int, Module] = {}
        test_map: dict[int, Test] = {}
        for old_mod in course.modules.order_by("order"):
            new_mod = Module.objects.create(
                course=new_course,
                title=old_mod.title,
                description=old_mod.description,
                order=old_mod.order,
            )
            module_map[old_mod.id] = new_mod
            for old_test in old_mod.tests.order_by("order"):
                new_test = Test.objects.create(
                    module=new_mod,
                    title=old_test.title,
                    description=old_test.description,
                    passing_score=old_test.passing_score,
                    duration_minutes=old_test.duration_minutes,
                    allow_retakes=old_test.allow_retakes,
                    max_attempts=old_test.max_attempts,
                    order=old_test.order,
                )
                test_map[old_test.id] = new_test
                for old_q in old_test.questions.order_by("order"):
                    Question.objects.create(
                        test=new_test,
                        question_type=old_q.question_type,
                        text=old_q.text,
                        options=old_q.options,
                        correct_indices=old_q.correct_indices,
                        correct_bool=old_q.correct_bool,
                        sample_answer=old_q.sample_answer,
                        accepted_answers=old_q.accepted_answers,
                        order=old_q.order,
                    )

        # Second pass: copy lessons and their items, now that every test exists.
        for old_mod in course.modules.order_by("order"):
            new_mod = module_map[old_mod.id]
            for old_lesson in old_mod.lessons.order_by("order"):
                new_lesson = Lesson.objects.create(
                    module=new_mod,
                    title=old_lesson.title,
                    duration_minutes=old_lesson.duration_minutes,
                    min_score=old_lesson.min_score,
                    is_preview=old_lesson.is_preview,
                    meeting_url=old_lesson.meeting_url,
                    order=old_lesson.order,
                )
                for old_item in old_lesson.items.order_by("order"):
                    new_item = LessonItem.objects.create(
                        lesson=new_lesson,
                        item_type=old_item.item_type,
                        order=old_item.order,
                        body_html=old_item.body_html,
                        video_url=old_item.video_url,
                        original_video_name=old_item.original_video_name,
                        duration_minutes=old_item.duration_minutes,
                        test=test_map.get(old_item.test_id),
                    )
                    if old_item.video:
                        duplicate_file_field(old_item.video, new_item.video)
                        new_item.video_hash = old_item.video_hash
                        new_item.save(update_fields=["video", "video_hash"])

        return new_course

    @classmethod
    @transaction.atomic
    def clone_for_pending_edit(cls, course: Course) -> Course:
        """Deep-copy a published/hidden course into a hidden PENDING_EDIT shadow draft."""
        draft = Course.all_objects.create(
            title=course.title,
            slug=cls._build_unique_slug(course.title),
            subtitle=course.subtitle,
            short_description=course.short_description,
            full_description=course.full_description,
            level=course.level,
            language=course.language,
            mode=course.mode,
            delivery_type=course.delivery_type,
            course_type=course.course_type,
            duration_hours=course.duration_hours,
            with_certificate=course.with_certificate,
            certificate_description=course.certificate_description,
            is_on_sale=course.is_on_sale,
            discount_percent=course.discount_percent,
            passing_score=course.passing_score,
            status=Course.StatusChoices.PENDING_EDIT,
            teacher_profile=course.teacher_profile,
            category=course.category,
        )
        if course.image:
            duplicate_file_field(course.image, draft.image)
            draft.image_hash = course.image_hash
            draft.save(update_fields=["image", "image_hash"])
        draft.tags.set(course.tags.all())

        module_map: dict[int, Module] = {}
        test_map: dict[int, Test] = {}
        for old_mod in course.modules.order_by("order"):
            new_mod = Module.objects.create(
                course=draft,
                source_module=old_mod,
                title=old_mod.title,
                description=old_mod.description,
                order=old_mod.order,
            )
            module_map[old_mod.id] = new_mod
            for old_test in old_mod.tests.order_by("order"):
                new_test = Test.objects.create(
                    module=new_mod,
                    source_test=old_test,
                    title=old_test.title,
                    description=old_test.description,
                    passing_score=old_test.passing_score,
                    duration_minutes=old_test.duration_minutes,
                    allow_retakes=old_test.allow_retakes,
                    max_attempts=old_test.max_attempts,
                    order=old_test.order,
                )
                test_map[old_test.id] = new_test
                for old_q in old_test.questions.order_by("order"):
                    Question.objects.create(
                        test=new_test,
                        source_question=old_q,
                        question_type=old_q.question_type,
                        text=old_q.text,
                        options=old_q.options,
                        correct_indices=old_q.correct_indices,
                        correct_bool=old_q.correct_bool,
                        sample_answer=old_q.sample_answer,
                        accepted_answers=old_q.accepted_answers,
                        order=old_q.order,
                    )

        # Second pass: lessons + items + documents, now that every test exists.
        for old_mod in course.modules.order_by("order"):
            new_mod = module_map[old_mod.id]
            for old_lesson in old_mod.lessons.order_by("order"):
                new_lesson = Lesson.objects.create(
                    module=new_mod,
                    source_lesson=old_lesson,
                    title=old_lesson.title,
                    duration_minutes=old_lesson.duration_minutes,
                    min_score=old_lesson.min_score,
                    is_preview=old_lesson.is_preview,
                    meeting_url=old_lesson.meeting_url,
                    unlock_after_days=old_lesson.unlock_after_days,
                    requires_previous=old_lesson.requires_previous,
                    is_manually_locked=old_lesson.is_manually_locked,
                    is_mandatory=old_lesson.is_mandatory,
                    order=old_lesson.order,
                )
                for old_item in old_lesson.items.order_by("order"):
                    new_item = LessonItem.objects.create(
                        lesson=new_lesson,
                        source_lesson_item=old_item,
                        item_type=old_item.item_type,
                        order=old_item.order,
                        body_html=old_item.body_html,
                        video_url=old_item.video_url,
                        original_video_name=old_item.original_video_name,
                        duration_minutes=old_item.duration_minutes,
                        test=test_map.get(old_item.test_id),
                    )
                    if old_item.video:
                        duplicate_file_field(old_item.video, new_item.video)
                        new_item.video_hash = old_item.video_hash
                        new_item.save(update_fields=["video", "video_hash"])
                for old_doc in old_lesson.documents.all():
                    new_doc = LessonDocument.objects.create(
                        lesson=new_lesson,
                        source_document=old_doc,
                        original_name=old_doc.original_name,
                    )
                    duplicate_file_field(old_doc.file, new_doc.file)
                    new_doc.save(update_fields=["file"])

        return draft

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
            except CoursePendingEdit.DoesNotExist as exc:
                raise CoursesError("This published course has no pending edit to assign.") from exc
            if pending_edit.status != CoursePendingEdit.StatusChoices.PENDING:
                raise CoursesError("The pending edit is not submitted for moderation yet.")
            if pending_edit.moderator_profile_id is not None:
                raise CoursesError("This pending edit already has a moderator assigned.")
            pending_edit.moderator_profile = moderator_profile
            pending_edit.save(update_fields=["moderator_profile"])
            return course

        raise CoursesError(
            "Only courses in 'review' or published courses with pending edits can be assigned."
        )

    @classmethod
    def get_teacher_courses_queryset(cls, teacher_profile):
        return cls.annotate_min_price(
            teacher_profile.courses.exclude(status=Course.StatusChoices.PENDING_EDIT)
            .select_related("teacher_profile__user", "category")
            .prefetch_related("tags")
        )

    @classmethod
    def get_enrolled_courses_queryset(cls, student_profile):
        # with_visible_access (not with_active_access) so a suspended course
        # (overdue installment) stays listed instead of vanishing from "my
        # courses"; enrollment_access_status lets the frontend show why.
        visible_enrollments = Enrollment.objects.with_visible_access().filter(
            student_profile=student_profile,
        )
        enrolled_at_subquery = visible_enrollments.filter(
            course_id=OuterRef("pk"),
        ).values("access_granted_at")[:1]
        completed_subquery = visible_enrollments.filter(
            course_id=OuterRef("pk"),
        ).values("lessons_completed_count")[:1]
        access_status_subquery = visible_enrollments.filter(
            course_id=OuterRef("pk"),
        ).values("access_status")[:1]

        queryset = (
            Course.objects.filter(
                pk__in=visible_enrollments.values_list("course_id", flat=True),
            )
            .select_related("teacher_profile__user", "category")
            .prefetch_related("tags")
            .annotate(
                enrolled_at=Subquery(enrolled_at_subquery),
                enrollment_lessons_completed=Subquery(completed_subquery),
                enrollment_access_status=Subquery(access_status_subquery),
            )
        )
        return cls.annotate_min_price(queryset)

    @classmethod
    def get_new_courses(
        cls,
        limit: int = DEFAULT_NEW_COURSES_LIMIT,
        context: dict | None = None,
    ) -> list[dict]:
        queryset = (
            Course.objects.filter(status=Course.StatusChoices.PUBLISHED)
            .select_related("teacher_profile__user", "category")
            .prefetch_related("tags")
        )
        courses = cls.annotate_min_price(queryset).order_by("-published_at")[:limit]
        return PublicCourseListSerializer(
            courses,
            many=True,
            context=context or {},
        ).data

    @classmethod
    def get_popular_courses(
        cls,
        limit: int = DEFAULT_POPULAR_COURSES_LIMIT,
        context: dict | None = None,
    ) -> list[dict]:
        # Popularity is the rolling 30-day enrollment count, not lifetime
        # students_count, so a course that was hot last year doesn't crowd
        # out something gaining traction this month. rating_avg is the
        # tiebreaker for cold-start courses with zero recent enrollments.
        queryset = (
            Course.objects.filter(status=Course.StatusChoices.PUBLISHED)
            .select_related("teacher_profile__user", "category")
            .prefetch_related("tags")
        )
        queryset = cls.annotate_min_price(queryset)
        queryset = cls.annotate_recent_enrollments(queryset)
        courses = queryset.order_by(
            "-students_enrolled_last_30_days",
            "-rating_avg",
        )[:limit]
        return PublicCourseListSerializer(
            courses,
            many=True,
            context=context or {},
        ).data

    @staticmethod
    def get_categories(
        limit: int = DEFAULT_FEATURED_CATEGORIES_LIMIT,
        context: dict | None = None,
    ) -> list[dict]:
        categories = CategoryService.annotate_public_courses_count(
            Category.objects.filter(featured_order__isnull=False)
        ).order_by("featured_order", "name_en")[:limit]
        return PublicCategorySerializer(
            categories,
            many=True,
            context=context or {},
        ).data

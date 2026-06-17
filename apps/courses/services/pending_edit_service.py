import os

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.courses.exceptions import PendingEditLockedError
from apps.courses.models import (
    ApprovedCourseRecord,
    CoursePendingEdit,
    ModerationReview,
    RejectedCourseRecord,
)
from apps.courses.services.course_service import _course_snapshot_kwargs
from apps.curriculum.models import Lesson, Module, Question, Test


def compute_pending_edit_changed_fields(pending_edit) -> list[str]:
    """Return the list of field names that differ between the pending edit and the live course."""
    course = pending_edit.course
    if not course:
        return []
    changed = []
    for field in [
        "title", "subtitle", "short_description", "full_description",
        "level", "language", "mode", "delivery_type", "course_type",
        "duration_hours", "with_certificate", "is_on_sale",
    ]:
        if getattr(pending_edit, field) != getattr(course, field):
            changed.append(field)
    if pending_edit.category_id != course.category_id:
        changed.append("category")
    live_tags = set(course.tags.values_list("id", flat=True))
    if set(pending_edit.tag_ids or []) != live_tags:
        changed.append("tags")
    if pending_edit.image and pending_edit.image.name != (course.image.name if course.image else None):
        changed.append("image")
    return changed


def _restore_or_create(Model, parent_lookup: dict, id_val, **kwargs):
    if id_val:
        obj = Model.all_objects.filter(id=id_val, **parent_lookup).first()
        if obj:
            for k, v in kwargs.items():
                setattr(obj, k, v)
            obj.is_deleted = False
            obj.save()
            return obj
    return Model.objects.create(**parent_lookup, **kwargs)


class PendingEditService:

    @staticmethod
    def _build_modules_snapshot(course) -> list:
        modules = (
            course.modules
            .prefetch_related("lessons", "lessons__items", "tests", "tests__questions")
            .order_by("order")
        )
        result = []
        for mod in modules:
            lessons = [
                {
                    "id": lesson.id,
                    "title": lesson.title,
                    "duration_minutes": lesson.duration_minutes,
                    "min_score": lesson.min_score,
                    "is_preview": lesson.is_preview,
                    "order": lesson.order,
                    "items_snapshot": [
                        {
                            "id": item.id,
                            "item_type": item.item_type,
                            "content": item.content or "",
                            "video_url": item.video_url,
                        }
                        for item in lesson.items.all()
                    ],
                }
                for lesson in mod.lessons.order_by("order")
            ]
            tests = []
            for test in mod.tests.order_by("order"):
                questions = [
                    {
                        "id": q.id,
                        "question_type": q.question_type,
                        "text": q.text,
                        "options": q.options or [],
                        "correct_index": q.correct_index,
                        "correct_bool": q.correct_bool,
                        "sample_answer": q.sample_answer or "",
                        "order": q.order,
                    }
                    for q in test.questions.order_by("order")
                ]
                tests.append({
                    "id": test.id,
                    "title": test.title,
                    "description": test.description,
                    "passing_score": test.passing_score,
                    "order": test.order,
                    "questions": questions,
                })
            result.append({
                "id": mod.id,
                "title": mod.title,
                "description": mod.description,
                "order": mod.order,
                "lessons": lessons,
                "tests": tests,
            })
        return result

    @classmethod
    def get_or_create(cls, course) -> CoursePendingEdit:
        try:
            return course.pending_edit
        except CoursePendingEdit.DoesNotExist:
            return cls._create_from_course(course)

    @classmethod
    def _create_from_course(cls, course) -> CoursePendingEdit:
        return CoursePendingEdit.objects.create(
            course=course,
            title=course.title,
            subtitle=course.subtitle or "",
            short_description=course.short_description,
            full_description=course.full_description,
            level=course.level,
            language=course.language,
            mode=course.mode,
            delivery_type=course.delivery_type,
            course_type=course.course_type,
            duration_hours=course.duration_hours,
            with_certificate=course.with_certificate,
            is_on_sale=course.is_on_sale,
            category=course.category,
            tag_ids=list(course.tags.values_list("id", flat=True)),
            modules_snapshot=cls._build_modules_snapshot(course),
        )

    @staticmethod
    def _ensure_editable(pending_edit: CoursePendingEdit) -> None:
        if pending_edit.status == CoursePendingEdit.StatusChoices.PENDING:
            raise PendingEditLockedError(
                "Cannot edit while pending moderation. Withdraw first."
            )

    @classmethod
    def update_metadata(cls, pending_edit: CoursePendingEdit, validated_data: dict) -> CoursePendingEdit:
        cls._ensure_editable(pending_edit)
        for attr, value in validated_data.items():
            setattr(pending_edit, attr, value)
        pending_edit.save()
        return pending_edit

    @classmethod
    def update_modules_snapshot(cls, pending_edit: CoursePendingEdit, modules_data: list) -> CoursePendingEdit:
        cls._ensure_editable(pending_edit)
        # Preserve items_snapshot from the original snapshot so the moderator
        # can always compare against the state at pending-edit creation time.
        existing_lessons = {
            lesson["id"]: lesson
            for mod in (pending_edit.modules_snapshot or [])
            for lesson in mod.get("lessons", [])
            if lesson.get("id") is not None
        }
        for mod in modules_data:
            for lesson in mod.get("lessons", []):
                lesson_id = lesson.get("id")
                if lesson_id is not None and "items_snapshot" not in lesson:
                    existing = existing_lessons.get(lesson_id, {})
                    if "items_snapshot" in existing:
                        lesson["items_snapshot"] = existing["items_snapshot"]
        pending_edit.modules_snapshot = modules_data
        pending_edit.save(update_fields=["modules_snapshot", "updated_at"])
        return pending_edit

    @staticmethod
    def submit(pending_edit: CoursePendingEdit) -> CoursePendingEdit:
        if pending_edit.status == CoursePendingEdit.StatusChoices.PENDING:
            raise PendingEditLockedError("Already submitted for moderation.")
        pending_edit.status = CoursePendingEdit.StatusChoices.PENDING
        pending_edit.submitted_at = timezone.now()
        pending_edit.save(update_fields=["status", "submitted_at", "updated_at"])
        pending_edit.course.save(update_fields=["updated_at"])
        return pending_edit

    @staticmethod
    def withdraw(pending_edit: CoursePendingEdit) -> CoursePendingEdit:
        if pending_edit.status != CoursePendingEdit.StatusChoices.PENDING:
            raise PendingEditLockedError("Can only withdraw when pending moderation.")
        pending_edit.status = CoursePendingEdit.StatusChoices.DRAFT
        pending_edit.save(update_fields=["status", "updated_at"])
        return pending_edit

    @staticmethod
    @transaction.atomic
    def discard(pending_edit: CoursePendingEdit) -> None:
        ModerationReview.objects.filter(course=pending_edit.course).delete()
        pending_edit.delete()

    @classmethod
    @transaction.atomic
    def approve(cls, pending_edit: CoursePendingEdit, moderator_profile=None) -> None:
        course = pending_edit.course
        changed = compute_pending_edit_changed_fields(pending_edit)

        for field in [
            "title", "subtitle", "short_description", "full_description",
            "level", "language", "mode", "delivery_type", "course_type",
            "duration_hours", "with_certificate", "is_on_sale", "category",
        ]:
            setattr(course, field, getattr(pending_edit, field))

        if pending_edit.image:
            ext = os.path.splitext(pending_edit.image.name)[1] or ".png"
            pending_edit.image.open("rb")
            try:
                content = pending_edit.image.read()
            finally:
                pending_edit.image.close()
            course.image.save(f"icon{ext}", ContentFile(content), save=False)

        course.save()
        course.tags.set(pending_edit.tag_ids or [])
        cls._apply_modules_snapshot(course, pending_edit.modules_snapshot)

        effective_moderator = moderator_profile or pending_edit.moderator_profile
        ModerationReview.objects.filter(course=course).delete()
        ApprovedCourseRecord.objects.create(
            course=course,
            teacher_profile=course.teacher_profile,
            moderator_profile=effective_moderator,
            **_course_snapshot_kwargs(course),
            changed_fields=changed,
        )
        pending_edit.delete()

    @staticmethod
    @transaction.atomic
    def reject(
        pending_edit: CoursePendingEdit,
        moderator_profile=None,
        basics_field_statuses: dict | None = None,
        basics_action: str = "",
        basics_comment: str = "",
        content_item_statuses: dict | None = None,
        content_action: str = "",
        content_comment: str = "",
        final_action: str = "",
        final_comment: str = "",
    ) -> CoursePendingEdit:
        course = pending_edit.course
        effective_moderator = moderator_profile or pending_edit.moderator_profile

        changed = compute_pending_edit_changed_fields(pending_edit)
        RejectedCourseRecord.objects.create(
            course=course,
            teacher_profile=course.teacher_profile,
            moderator_profile=effective_moderator,
            **_course_snapshot_kwargs(course),
            changed_fields=changed,
            basics_field_statuses=basics_field_statuses or {},
            basics_action=basics_action,
            basics_comment=basics_comment or "",
            content_item_statuses=content_item_statuses or {},
            content_action=content_action,
            content_comment=content_comment or "",
            final_action=final_action,
            final_comment=final_comment or "",
        )

        if final_action == "rejected":
            # Full rejection: discard the draft entirely; live course is untouched.
            ModerationReview.objects.filter(course=course).delete()
            pending_edit.delete()
            return pending_edit

        # needs_revision: keep the draft so the teacher can fix and resubmit.
        pending_edit.status = CoursePendingEdit.StatusChoices.NEEDS_REVISION
        pending_edit.moderator_comment = final_comment
        pending_edit.save(update_fields=["status", "moderator_comment", "updated_at"])

        ModerationReview.objects.update_or_create(
            course=course,
            defaults={
                "moderator_profile": effective_moderator,
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
        return pending_edit

    @staticmethod
    @transaction.atomic
    def _apply_modules_snapshot(course, modules_data: list) -> None:
        # Soft-delete all active modules first so their orders don't conflict during restore.
        Module.all_objects.filter(course=course, is_deleted=False).update(is_deleted=True)

        for idx, mod_data in enumerate(modules_data, 1):
            module = _restore_or_create(
                Module,
                {"course": course},
                mod_data.get("id"),
                title=mod_data.get("title", ""),
                description=mod_data.get("description", ""),
                order=mod_data.get("order", idx),
            )

            Lesson.all_objects.filter(module=module, is_deleted=False).update(is_deleted=True)
            for l_idx, lesson_data in enumerate(mod_data.get("lessons", []), 1):
                _restore_or_create(
                    Lesson,
                    {"module": module},
                    lesson_data.get("id"),
                    title=lesson_data.get("title", ""),
                    duration_minutes=lesson_data.get("duration_minutes"),
                    min_score=lesson_data.get("min_score"),
                    is_preview=lesson_data.get("is_preview", False),
                    order=lesson_data.get("order", l_idx),
                )

            Test.all_objects.filter(module=module, is_deleted=False).update(is_deleted=True)
            for t_idx, test_data in enumerate(mod_data.get("tests", []), 1):
                test = _restore_or_create(
                    Test,
                    {"module": module},
                    test_data.get("id"),
                    title=test_data.get("title", ""),
                    description=test_data.get("description", ""),
                    passing_score=test_data.get("passing_score", 70),
                    order=test_data.get("order", t_idx),
                )

                Question.all_objects.filter(test=test, is_deleted=False).update(is_deleted=True)
                for q_idx, q_data in enumerate(test_data.get("questions", []), 1):
                    _restore_or_create(
                        Question,
                        {"test": test},
                        q_data.get("id"),
                        question_type=q_data.get("question_type", "multiple_choice"),
                        text=q_data.get("text", ""),
                        options=q_data.get("options", []),
                        correct_index=q_data.get("correct_index"),
                        correct_bool=q_data.get("correct_bool"),
                        sample_answer=q_data.get("sample_answer", ""),
                        order=q_data.get("order", q_idx),
                    )

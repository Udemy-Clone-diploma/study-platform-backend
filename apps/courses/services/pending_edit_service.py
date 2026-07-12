import os

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.common.files import duplicate_file_field
from apps.courses.exceptions import PendingEditLockedError
from apps.courses.models import (
    ApprovedCourseRecord,
    CoursePendingEdit,
    ModerationReview,
    RejectedCourseRecord,
)
from apps.courses.services.course_service import CourseService, _course_snapshot_kwargs
from apps.curriculum.models import Lesson, LessonDocument, LessonItem, Module, Question, Test


def compute_pending_edit_changed_fields(pending_edit) -> list[str]:
    """Return the list of course field names that differ between the draft and the live course."""
    course = pending_edit.course
    draft = pending_edit.draft_course
    if not course or not draft:
        return []
    changed = []
    for field in [
        "title", "subtitle", "short_description", "full_description",
        "level", "language", "mode", "delivery_type", "course_type",
        "with_certificate", "certificate_description", "is_on_sale", "passing_score",
    ]:
        if getattr(draft, field) != getattr(course, field):
            changed.append(field)
    if draft.category_id != course.category_id:
        changed.append("category")
    draft_tags = set(draft.tags.values_list("id", flat=True))
    live_tags = set(course.tags.values_list("id", flat=True))
    if draft_tags != live_tags:
        changed.append("tags")
    if draft.image_hash != course.image_hash:
        changed.append("image")
    return changed


def _merge_row(Model, live_parent_lookup: dict, source_id, **kwargs):
    """Update-in-place (and undelete) the live row referenced by source_id, or
    create a brand-new live row if there's no source (new-since-clone content)."""
    if source_id:
        obj = Model.all_objects.filter(id=source_id, **live_parent_lookup).first()
        if obj:
            for k, v in kwargs.items():
                setattr(obj, k, v)
            obj.is_deleted = False
            # Explicit update_fields (rather than a bare save()) matters beyond
            # the query itself: LessonItem.save() only recomputes video_hash
            # when "video" is among the saved fields, and video isn't touched
            # here (it's merged separately, right after) -- a bare save() would
            # force a full re-read+re-hash of whatever video the live row
            # already has, for every single merged item, on every approval.
            obj.save(update_fields=[*kwargs.keys(), "is_deleted", "updated_at"])
            return obj
    return Model.objects.create(**live_parent_lookup, **kwargs)


def _merge_document(live_lesson, draft_doc) -> LessonDocument:
    """LessonDocument has no is_deleted field """
    if draft_doc.source_document_id:
        doc = LessonDocument.objects.filter(id=draft_doc.source_document_id, lesson=live_lesson).first()
        if doc:
            duplicate_file_field(draft_doc.file, doc.file)
            doc.original_name = draft_doc.original_name
            doc.save()
            return doc
    doc = LessonDocument.objects.create(
        lesson=live_lesson,
        original_name=draft_doc.original_name,
    )
    duplicate_file_field(draft_doc.file, doc.file)
    doc.save(update_fields=["file"])
    return doc


class PendingEditService:

    @classmethod
    def get_or_create(cls, course) -> CoursePendingEdit:
        try:
            return course.pending_edit
        except CoursePendingEdit.DoesNotExist:
            return cls._create_from_course(course)

    @classmethod
    def _create_from_course(cls, course) -> CoursePendingEdit:
        draft = CourseService.clone_for_pending_edit(course)
        return CoursePendingEdit.objects.create(course=course, draft_course=draft)

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
        # Release the assigned moderator too — withdrawing abandons this review
        # cycle entirely, so resubmitting later should land back in the
        # unassigned pool rather than staying privately assigned to whoever
        # had it before (unlike needs_revision, where the same moderator
        # continuing to handle the resubmission is the desired behavior).
        pending_edit.status = CoursePendingEdit.StatusChoices.DRAFT
        pending_edit.moderator_profile = None
        pending_edit.save(update_fields=["status", "moderator_profile", "updated_at"])
        return pending_edit

    @staticmethod
    @transaction.atomic
    def discard(pending_edit: CoursePendingEdit) -> None:
        ModerationReview.objects.filter(course=pending_edit.course).delete()
        draft = pending_edit.draft_course
        pending_edit.delete()
        draft.delete()

    @classmethod
    @transaction.atomic
    def approve(cls, pending_edit: CoursePendingEdit, moderator_profile=None) -> None:
        course = pending_edit.course
        draft = pending_edit.draft_course
        changed = compute_pending_edit_changed_fields(pending_edit)

        for field in [
            "title", "subtitle", "short_description", "full_description",
            "level", "language", "mode", "delivery_type", "course_type",
            "with_certificate", "certificate_description", "is_on_sale", "passing_score",
        ]:
            setattr(course, field, getattr(draft, field))
        course.category = draft.category

        if draft.image:
            ext = os.path.splitext(draft.image.name)[1] or ".png"
            draft.image.open("rb")
            try:
                content = draft.image.read()
            finally:
                draft.image.close()
            course.image.save(f"icon{ext}", ContentFile(content), save=False)

        course.save()
        course.tags.set(draft.tags.all())
        cls.merge_into_live(pending_edit)

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
        draft.delete()

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
            draft = pending_edit.draft_course
            pending_edit.delete()
            draft.delete()
            return pending_edit

        # needs_revision: keep the draft as-is so the teacher can fix and resubmit
        # the same rows — do not re-clone, or in-progress edits would be lost.
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

    @classmethod
    @transaction.atomic
    def merge_into_live(cls, pending_edit: CoursePendingEdit) -> None:
        """Merge the draft course's current tree onto the live course.

        For each draft row: if it has a source_* pointing at a live row, that live
        row is updated in place (same id — preserves LessonCompletion/Note/etc FKs);
        otherwise a new live row is created. Live rows soft-deleted up front and not
        re-claimed by any draft row stay deleted (removed by the teacher in the draft).
        """
        live_course = pending_edit.course
        draft_course = pending_edit.draft_course

        Module.all_objects.filter(course=live_course, is_deleted=False).update(is_deleted=True)

        for idx, draft_mod in enumerate(draft_course.modules.order_by("order"), 1):
            live_mod = _merge_row(
                Module, {"course": live_course}, draft_mod.source_module_id,
                title=draft_mod.title, description=draft_mod.description, order=idx,
            )

            # Tests before lessons: LessonItem.test needs the live test's id, resolved
            # below through test_map (keyed by the draft test's own id).
            Test.all_objects.filter(module=live_mod, is_deleted=False).update(is_deleted=True)
            test_map: dict[int, Test] = {}
            for t_idx, draft_test in enumerate(draft_mod.tests.order_by("order"), 1):
                live_test = _merge_row(
                    Test, {"module": live_mod}, draft_test.source_test_id,
                    title=draft_test.title, description=draft_test.description,
                    passing_score=draft_test.passing_score, duration_minutes=draft_test.duration_minutes,
                    allow_retakes=draft_test.allow_retakes, max_attempts=draft_test.max_attempts,
                    order=t_idx,
                )
                test_map[draft_test.id] = live_test

                Question.all_objects.filter(test=live_test, is_deleted=False).update(is_deleted=True)
                for q_idx, draft_q in enumerate(draft_test.questions.order_by("order"), 1):
                    _merge_row(
                        Question, {"test": live_test}, draft_q.source_question_id,
                        question_type=draft_q.question_type, text=draft_q.text,
                        options=draft_q.options, correct_indices=draft_q.correct_indices,
                        correct_bool=draft_q.correct_bool, sample_answer=draft_q.sample_answer,
                        accepted_answers=draft_q.accepted_answers, order=q_idx,
                    )

            Lesson.all_objects.filter(module=live_mod, is_deleted=False).update(is_deleted=True)
            for l_idx, draft_lesson in enumerate(draft_mod.lessons.order_by("order"), 1):
                live_lesson = _merge_row(
                    Lesson, {"module": live_mod}, draft_lesson.source_lesson_id,
                    title=draft_lesson.title, duration_minutes=draft_lesson.duration_minutes,
                    min_score=draft_lesson.min_score, is_preview=draft_lesson.is_preview,
                    meeting_url=draft_lesson.meeting_url,
                    unlock_after_days=draft_lesson.unlock_after_days,
                    requires_previous=draft_lesson.requires_previous,
                    is_manually_locked=draft_lesson.is_manually_locked,
                    is_mandatory=draft_lesson.is_mandatory,
                    order=l_idx,
                )

                LessonItem.all_objects.filter(lesson=live_lesson, is_deleted=False).update(is_deleted=True)
                for i_idx, draft_item in enumerate(draft_lesson.items.order_by("order"), 1):
                    live_item = _merge_row(
                        LessonItem, {"lesson": live_lesson}, draft_item.source_lesson_item_id,
                        item_type=draft_item.item_type, order=i_idx,
                        body_html=draft_item.body_html,
                        video_url=draft_item.video_url,
                        original_video_name=draft_item.original_video_name,
                        duration_minutes=draft_item.duration_minutes,
                        test=test_map.get(draft_item.test_id),
                    )
                    
                    if draft_item.video:
                        duplicate_file_field(draft_item.video, live_item.video)
                        live_item.video_hash = draft_item.video_hash
                        live_item.save(update_fields=["video", "video_hash"])
                    elif live_item.video:
                        live_item.video = None
                        live_item.save(update_fields=["video"])

                matched_doc_ids = {
                    _merge_document(live_lesson, draft_doc).id
                    for draft_doc in draft_lesson.documents.all()
                }
                LessonDocument.objects.filter(lesson=live_lesson).exclude(id__in=matched_doc_ids).delete()

from django.db import transaction
from django.utils import timezone

from apps.courses.exceptions import PendingEditLockedError
from apps.courses.models import CoursePendingEdit


class PendingEditService:

    # ------------------------------------------------------------------ #
    # Snapshot builders                                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_modules_snapshot(course) -> list:
        modules = (
            course.modules
            .prefetch_related("lessons", "tests", "tests__questions")
            .order_by("order")
        )
        result = []
        for mod in modules:
            lessons = [
                {
                    "id": lesson.id,
                    "title": lesson.title,
                    "content": lesson.content,
                    "video_url": lesson.video_url,
                    "body_html": lesson.body_html or "",
                    "duration_minutes": lesson.duration_minutes,
                    "min_score": lesson.min_score,
                    "is_preview": lesson.is_preview,
                    "content_type": lesson.content_type,
                    "order": lesson.order,
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

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

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

    # ------------------------------------------------------------------ #
    # Guards                                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _ensure_editable(pending_edit: CoursePendingEdit) -> None:
        if pending_edit.status == CoursePendingEdit.StatusChoices.PENDING:
            raise PendingEditLockedError(
                "Cannot edit while pending moderation. Withdraw first."
            )

    # ------------------------------------------------------------------ #
    # Teacher actions                                                      #
    # ------------------------------------------------------------------ #

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
        return pending_edit

    @staticmethod
    def withdraw(pending_edit: CoursePendingEdit) -> CoursePendingEdit:
        """Withdraw from moderation; keeps the draft edits, returns to editable state."""
        if pending_edit.status != CoursePendingEdit.StatusChoices.PENDING:
            raise PendingEditLockedError("Can only withdraw when pending moderation.")
        pending_edit.status = CoursePendingEdit.StatusChoices.DRAFT
        pending_edit.save(update_fields=["status", "updated_at"])
        return pending_edit

    @staticmethod
    def discard(pending_edit: CoursePendingEdit) -> None:
        """Delete the pending edit entirely. The published course is unaffected."""
        pending_edit.delete()

    # ------------------------------------------------------------------ #
    # Moderator actions                                                    #
    # ------------------------------------------------------------------ #

    @classmethod
    @transaction.atomic
    def approve(cls, pending_edit: CoursePendingEdit) -> None:
        """Apply all pending changes to the live course and remove the draft."""
        course = pending_edit.course

        for field in [
            "title", "subtitle", "short_description", "full_description",
            "level", "language", "mode", "delivery_type", "course_type",
            "duration_hours", "with_certificate", "is_on_sale", "category",
        ]:
            setattr(course, field, getattr(pending_edit, field))

        if pending_edit.image:
            course.image = pending_edit.image

        course.save()
        course.tags.set(pending_edit.tag_ids or [])

        cls._apply_modules_snapshot(course, pending_edit.modules_snapshot)

        pending_edit.delete()

    @staticmethod
    def reject(pending_edit: CoursePendingEdit, comment: str = "") -> CoursePendingEdit:
        pending_edit.status = CoursePendingEdit.StatusChoices.NEEDS_REVISION
        pending_edit.moderator_comment = comment
        pending_edit.save(update_fields=["status", "moderator_comment", "updated_at"])
        return pending_edit

    # ------------------------------------------------------------------ #
    # Snapshot application (used during approve)                          #
    # ------------------------------------------------------------------ #

    @staticmethod
    @transaction.atomic
    def _apply_modules_snapshot(course, modules_data: list) -> None:
        from apps.curriculum.models import Lesson, Module, Test
        from apps.curriculum.models.Question import Question

        # Soft-delete all active modules so their orders don't conflict during restore.
        # Lessons/tests are left untouched at this point; they'll be handled per-module.
        Module.all_objects.filter(course=course, is_deleted=False).update(is_deleted=True)

        for idx, mod_data in enumerate(modules_data, 1):
            mod_id = mod_data.get("id")
            order = mod_data.get("order", idx)

            if mod_id:
                module = Module.all_objects.filter(id=mod_id, course=course).first()
                if module:
                    module.title = mod_data.get("title", "")
                    module.description = mod_data.get("description", "")
                    module.order = order
                    module.is_deleted = False
                    module.save()
                else:
                    module = Module.objects.create(
                        course=course,
                        title=mod_data.get("title", ""),
                        description=mod_data.get("description", ""),
                        order=order,
                    )
            else:
                module = Module.objects.create(
                    course=course,
                    title=mod_data.get("title", ""),
                    description=mod_data.get("description", ""),
                    order=order,
                )

            # Soft-delete current active lessons; restore or create from snapshot
            Lesson.all_objects.filter(module=module, is_deleted=False).update(is_deleted=True)

            for l_idx, lesson_data in enumerate(mod_data.get("lessons", []), 1):
                lesson_id = lesson_data.get("id")
                lesson_kwargs = {
                    "title": lesson_data.get("title", ""),
                    "content": lesson_data.get("content", ""),
                    "video_url": lesson_data.get("video_url"),
                    "body_html": lesson_data.get("body_html", "") or "",
                    "duration_minutes": lesson_data.get("duration_minutes"),
                    "min_score": lesson_data.get("min_score"),
                    "is_preview": lesson_data.get("is_preview", False),
                    "content_type": lesson_data.get("content_type", "text"),
                    "order": lesson_data.get("order", l_idx),
                }
                if lesson_id:
                    lesson = Lesson.all_objects.filter(id=lesson_id, module=module).first()
                    if lesson:
                        for k, v in lesson_kwargs.items():
                            setattr(lesson, k, v)
                        lesson.is_deleted = False
                        lesson.save()
                    else:
                        Lesson.objects.create(module=module, **lesson_kwargs)
                else:
                    Lesson.objects.create(module=module, **lesson_kwargs)

            # Tests
            Test.all_objects.filter(module=module, is_deleted=False).update(is_deleted=True)

            for t_idx, test_data in enumerate(mod_data.get("tests", []), 1):
                test_id = test_data.get("id")
                test_kwargs = {
                    "title": test_data.get("title", ""),
                    "description": test_data.get("description", ""),
                    "passing_score": test_data.get("passing_score", 70),
                    "order": test_data.get("order", t_idx),
                }
                if test_id:
                    test = Test.all_objects.filter(id=test_id, module=module).first()
                    if test:
                        for k, v in test_kwargs.items():
                            setattr(test, k, v)
                        test.is_deleted = False
                        test.save()
                    else:
                        test = Test.objects.create(module=module, **test_kwargs)
                else:
                    test = Test.objects.create(module=module, **test_kwargs)

                # Questions: soft-delete all then restore/create
                Question.all_objects.filter(test=test, is_deleted=False).update(is_deleted=True)

                for q_idx, q_data in enumerate(test_data.get("questions", []), 1):
                    q_id = q_data.get("id")
                    q_kwargs = {
                        "question_type": q_data.get("question_type", "multiple_choice"),
                        "text": q_data.get("text", ""),
                        "options": q_data.get("options", []),
                        "correct_index": q_data.get("correct_index"),
                        "correct_bool": q_data.get("correct_bool"),
                        "sample_answer": q_data.get("sample_answer", ""),
                        "order": q_data.get("order", q_idx),
                    }
                    if q_id:
                        question = Question.all_objects.filter(id=q_id, test=test).first()
                        if question:
                            for k, v in q_kwargs.items():
                                setattr(question, k, v)
                            question.is_deleted = False
                            question.save()
                        else:
                            Question.objects.create(test=test, **q_kwargs)
                    else:
                        Question.objects.create(test=test, **q_kwargs)
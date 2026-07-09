from django.db.models import QuerySet

from apps.curriculum.models import Lesson, Note


class NoteService:
    @staticmethod
    def get_note(user, lesson: Lesson) -> Note | None:
        return Note.objects.filter(user=user, lesson=lesson).first()

    @staticmethod
    def list_notes_for_user(user) -> QuerySet[Note]:
        return (
            Note.objects.filter(user=user)
            .exclude(content="")
            .order_by("-updated_at")
        )

    @staticmethod
    def upsert_note(user, lesson: Lesson, content: str) -> Note:
        note, _ = Note.objects.update_or_create(
            user=user, lesson=lesson,
            defaults={
                "content": content,
                "course_id": lesson.module.course_id,
                "course_slug": lesson.module.course.slug,
                "course_title": lesson.module.course.title,
                "course_level": lesson.module.course.level,
                "module_title": lesson.module.title,
                "lesson_title": lesson.title,
                "lesson_order": lesson.order,
            },
        )
        return note

    @staticmethod
    def delete_note(user, lesson: Lesson) -> None:
        Note.objects.filter(user=user, lesson=lesson).delete()

from apps.curriculum.models import Lesson, Note


class NoteService:
    @staticmethod
    def get_note(user, lesson: Lesson) -> Note | None:
        return Note.objects.filter(user=user, lesson=lesson).first()

    @staticmethod
    def upsert_note(user, lesson: Lesson, content: str) -> Note:
        note, _ = Note.objects.update_or_create(
            user=user, lesson=lesson, defaults={"content": content},
        )
        return note

    @staticmethod
    def delete_note(user, lesson: Lesson) -> None:
        Note.objects.filter(user=user, lesson=lesson).delete()

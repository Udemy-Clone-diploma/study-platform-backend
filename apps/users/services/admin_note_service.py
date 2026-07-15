from apps.users.models import AdminNote, User


class AdminNoteService:
    @staticmethod
    def get_note(user: User) -> AdminNote | None:
        return AdminNote.objects.filter(user=user).first()

    @staticmethod
    def upsert_note(user: User, content: str, updated_by: User) -> AdminNote:
        note, _ = AdminNote.objects.update_or_create(
            user=user, defaults={"content": content, "updated_by": updated_by},
        )
        return note

    @staticmethod
    def delete_note(user: User) -> None:
        AdminNote.objects.filter(user=user).delete()

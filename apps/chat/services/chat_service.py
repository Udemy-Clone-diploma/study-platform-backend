from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.chat.models import ChatParticipant, ChatRoom, ChatUserBlock, ChatUserRestriction, Message
from apps.users.models import User


class ChatService:
    @staticmethod
    def assert_can_write(user) -> None:
        if ChatUserRestriction.objects.filter(user=user, is_active=True).exists():
            raise PermissionDenied("Your ability to write in chats has been restricted by moderation.")

    @staticmethod
    def direct_key_for_users(first_user_id: int, second_user_id: int) -> str:
        lower, higher = sorted((int(first_user_id), int(second_user_id)))
        return f"{lower}_{higher}"

    @staticmethod
    def active_participants(chat_id: int):
        return ChatParticipant.objects.filter(chat_id=chat_id, left_at__isnull=True)

    @staticmethod
    def active_participant_user_ids(chat_id: int) -> list[int]:
        return list(
            ChatService.active_participants(chat_id).values_list("user_id", flat=True)
        )

    @staticmethod
    def get_active_participation(user, chat_id: int) -> ChatParticipant:
        participation = (
            ChatParticipant.objects.select_related("chat")
            .filter(
                chat_id=chat_id,
                user=user,
                left_at__isnull=True,
                chat__is_deleted=False,
            )
            .first()
        )
        if participation is None:
            raise PermissionDenied("You are not an active participant of this chat.")
        return participation

    @staticmethod
    def is_active_participant(user, chat_id: int) -> bool:
        if not user or not user.is_authenticated:
            return False
        return ChatParticipant.objects.filter(
            chat_id=chat_id,
            user=user,
            left_at__isnull=True,
            chat__is_deleted=False,
        ).exists()

    @staticmethod
    def can_manage_participants(user, chat: ChatRoom) -> bool:
        return ChatParticipant.objects.filter(
            chat=chat,
            user=user,
            left_at__isnull=True,
            role__in=[
                ChatParticipant.RoleChoices.OWNER,
                ChatParticipant.RoleChoices.ADMIN,
            ],
        ).exists()

    @staticmethod
    def direct_peer_for_user(chat: ChatRoom, user) -> User:
        if chat.type != ChatRoom.TypeChoices.DIRECT:
            raise ValidationError("This action is only available for direct chats.")
        peer = (
            User.objects.filter(
                chat_participations__chat=chat,
                chat_participations__left_at__isnull=True,
            )
            .exclude(pk=user.pk)
            .first()
        )
        if peer is None:
            raise ValidationError("Direct chat peer was not found.")
        return peer

    @staticmethod
    def blocked_user_ids_for(user) -> list[int]:
        return list(ChatUserBlock.objects.filter(blocker=user).values_list("blocked_id", flat=True))

    @staticmethod
    def is_direct_chat_blocked(chat: ChatRoom, sender) -> bool:
        if chat.type != ChatRoom.TypeChoices.DIRECT:
            return False
        user_ids = list(
            ChatParticipant.objects.filter(chat=chat, left_at__isnull=True).values_list(
                "user_id",
                flat=True,
            )
        )
        if len(user_ids) < 2:
            return False
        peer_ids = [user_id for user_id in user_ids if user_id != sender.pk]
        return ChatUserBlock.objects.filter(
            Q(blocker_id=sender.pk, blocked_id__in=peer_ids)
            | Q(blocker_id__in=peer_ids, blocked_id=sender.pk)
        ).exists()

    @staticmethod
    def set_direct_peer_block(chat: ChatRoom, blocker, *, is_blocked: bool) -> tuple[User, bool]:
        ChatService.get_active_participation(blocker, chat.pk)
        blocked = ChatService.direct_peer_for_user(chat, blocker)
        if is_blocked:
            ChatUserBlock.objects.get_or_create(blocker=blocker, blocked=blocked)
            return blocked, True
        ChatUserBlock.objects.filter(blocker=blocker, blocked=blocked).delete()
        return blocked, False

    @staticmethod
    def set_mute(chat: ChatRoom, user, *, is_muted: bool) -> ChatParticipant:
        participation = ChatService.get_active_participation(user, chat.pk)
        participation.is_muted = is_muted
        participation.save(update_fields=["is_muted", "updated_at"])
        return participation

    @staticmethod
    def clear_history(chat: ChatRoom, user) -> ChatParticipant:
        participation = ChatService.get_active_participation(user, chat.pk)
        participation.history_cleared_at = timezone.now()
        participation.last_read_message = chat.last_message
        participation.save(
            update_fields=["history_cleared_at", "last_read_message", "updated_at"]
        )
        return participation

    @staticmethod
    def delete_chat_for_everyone(chat: ChatRoom) -> ChatRoom:
        chat.is_deleted = True
        chat.save(update_fields=["is_deleted", "updated_at"])
        ChatParticipant.objects.filter(chat=chat, left_at__isnull=True).update(
            left_at=timezone.now(),
            updated_at=timezone.now(),
        )
        return chat

    @staticmethod
    def create_direct_chat(created_by, other_user: User) -> tuple[ChatRoom, bool]:
        if created_by.pk == other_user.pk:
            raise ValidationError({"user_id": "You cannot start a direct chat with yourself."})

        direct_key = ChatService.direct_key_for_users(created_by.pk, other_user.pk)

        with transaction.atomic():
            try:
                chat, created = ChatRoom.objects.get_or_create(
                    direct_key=direct_key,
                    defaults={
                        "type": ChatRoom.TypeChoices.DIRECT,
                        "created_by": created_by,
                    },
                )
            except IntegrityError:
                chat = ChatRoom.objects.select_for_update().get(direct_key=direct_key)
                created = False

            if chat.is_deleted:
                chat.is_deleted = False
                chat.save(update_fields=["is_deleted", "updated_at"])

            for user in (created_by, other_user):
                participant, _ = ChatParticipant.objects.update_or_create(
                    chat=chat,
                    user=user,
                    defaults={
                        "role": ChatParticipant.RoleChoices.MEMBER,
                        "left_at": None,
                    },
                )
                if participant.left_at is not None:
                    participant.left_at = None
                    participant.save(update_fields=["left_at", "updated_at"])

        return chat, created

    @staticmethod
    def create_group_chat(
        created_by,
        title: str,
        participant_ids: list[int],
        image=None,
    ) -> ChatRoom:
        user_ids = list(dict.fromkeys([created_by.pk, *participant_ids]))
        users = list(User.objects.filter(pk__in=user_ids, is_deleted=False))
        if len(users) != len(user_ids):
            raise ValidationError({"participant_ids": "One or more users do not exist."})

        with transaction.atomic():
            chat = ChatRoom.objects.create(
                type=ChatRoom.TypeChoices.GROUP,
                title=title,
                created_by=created_by,
                image=image,
            )
            participants = []
            for user in users:
                role = (
                    ChatParticipant.RoleChoices.OWNER
                    if user.pk == created_by.pk
                    else ChatParticipant.RoleChoices.MEMBER
                )
                participants.append(ChatParticipant(chat=chat, user=user, role=role))
            ChatParticipant.objects.bulk_create(participants)

        return chat

    @staticmethod
    def _cohort_chat_title(cohort) -> str:
        group_name = cohort.name or "Study group"
        return f"{cohort.course.title} — {group_name}"[:255]

    @staticmethod
    def _delivery_format_chat_title(delivery_format) -> str:
        return (
            f"{delivery_format.course.title} — "
            f"{delivery_format.get_format_type_display()}"
        )[:255]

    @classmethod
    def ensure_cohort_chat(cls, cohort: "object") -> ChatRoom:
        """Return the cohort chat, creating it with the course teacher as owner.

        The relation on Cohort makes this operation idempotent. Existing cohort
        members are also synchronized so the helper is safe for legacy rows and
        for membership records created outside the HTTP view.
        """
        from apps.courses.models import Cohort, CohortMember

        with transaction.atomic():
            locked_cohort = (
                Cohort.objects.select_for_update()
                .select_related("course__teacher_profile__user")
                .get(pk=cohort.pk)
            )
            if locked_cohort.group_chat_id:
                chat = ChatRoom.objects.get(pk=locked_cohort.group_chat_id)
            else:
                chat = cls.create_group_chat(
                    created_by=locked_cohort.course.teacher_profile.user,
                    title=cls._cohort_chat_title(locked_cohort),
                    participant_ids=[],
                )
                Cohort.objects.filter(pk=locked_cohort.pk).update(group_chat_id=chat.pk)

            member_user_ids = list(
                CohortMember.objects.filter(cohort_id=locked_cohort.pk).values_list(
                    "enrollment__student_profile__user_id", flat=True
                )
            )

        cls.add_participants(chat, member_user_ids)
        cohort.group_chat_id = chat.pk
        return chat

    @classmethod
    def ensure_delivery_format_chat(cls, delivery_format: "object") -> ChatRoom | None:
        """Ensure the shared chat for self-paced and scheduled formats exists."""
        from apps.courses.models import CourseDeliveryFormat
        from apps.enrollments.models import Enrollment

        if delivery_format.format_type not in {
            CourseDeliveryFormat.FormatType.SELF_PACED,
            CourseDeliveryFormat.FormatType.SCHEDULED,
        }:
            return None

        with transaction.atomic():
            locked_format = (
                CourseDeliveryFormat.objects.select_for_update()
                .select_related("course__teacher_profile__user")
                .get(pk=delivery_format.pk)
            )
            if locked_format.group_chat_id:
                chat = ChatRoom.objects.get(pk=locked_format.group_chat_id)
            else:
                chat = cls.create_group_chat(
                    created_by=locked_format.course.teacher_profile.user,
                    title=cls._delivery_format_chat_title(locked_format),
                    participant_ids=[],
                )
                CourseDeliveryFormat.objects.filter(pk=locked_format.pk).update(
                    group_chat_id=chat.pk
                )

            student_user_ids = list(
                Enrollment.objects.with_active_access()
                .filter(delivery_format_id=locked_format.pk)
                .values_list("student_profile__user_id", flat=True)
            )

        cls.add_participants(chat, student_user_ids)
        delivery_format.group_chat_id = chat.pk
        return chat

    @staticmethod
    def add_participants(chat: ChatRoom, user_ids: list[int]) -> list[ChatParticipant]:
        if chat.type != ChatRoom.TypeChoices.GROUP:
            raise ValidationError("Participants can only be managed for group chats.")

        unique_user_ids = list(dict.fromkeys(user_ids))
        users = list(User.objects.filter(pk__in=unique_user_ids, is_deleted=False))
        if len(users) != len(unique_user_ids):
            raise ValidationError({"user_ids": "One or more users do not exist."})

        added = []
        with transaction.atomic():
            for user in users:
                participant, created = ChatParticipant.objects.update_or_create(
                    chat=chat,
                    user=user,
                    defaults={
                        "role": ChatParticipant.RoleChoices.MEMBER,
                        "left_at": None,
                    },
                )
                if created or participant.left_at is None:
                    added.append(participant)
            chat.save(update_fields=["updated_at"])
        return added

    @staticmethod
    def remove_participant(chat: ChatRoom, user_id: int) -> ChatParticipant:
        participant = get_object_or_404(
            ChatParticipant,
            chat=chat,
            user_id=user_id,
            left_at__isnull=True,
        )
        if participant.role == ChatParticipant.RoleChoices.OWNER:
            raise ValidationError("The owner cannot be removed from a group chat.")
        participant.left_at = timezone.now()
        participant.save(update_fields=["left_at", "updated_at"])
        chat.save(update_fields=["updated_at"])
        return participant

    @staticmethod
    def update_participant_role(
        chat: ChatRoom,
        user_id: int,
        role: str,
    ) -> ChatParticipant:
        if role == ChatParticipant.RoleChoices.OWNER:
            raise ValidationError({"role": "Owner role cannot be assigned here."})
        participant = get_object_or_404(
            ChatParticipant,
            chat=chat,
            user_id=user_id,
            left_at__isnull=True,
        )
        if participant.role == ChatParticipant.RoleChoices.OWNER:
            raise ValidationError("The owner role cannot be changed.")
        participant.role = role
        participant.save(update_fields=["role", "updated_at"])
        chat.save(update_fields=["updated_at"])
        return participant

    @staticmethod
    def create_message(
        chat: ChatRoom,
        sender,
        *,
        text: str,
        message_type: str = Message.TypeChoices.TEXT,
        reply_to: Message | None = None,
    ) -> Message:
        ChatService.assert_can_write(sender)
        ChatService.get_active_participation(sender, chat.pk)
        if chat.is_read_only:
            raise PermissionDenied("This is an official read-only chat.")
        if ChatService.is_direct_chat_blocked(chat, sender):
            raise PermissionDenied("Messages are blocked in this chat.")
        if reply_to is not None and reply_to.chat_id != chat.pk:
            raise ValidationError({"reply_to": "Reply target must belong to this chat."})

        with transaction.atomic():
            message = Message.objects.create(
                chat=chat,
                sender=sender,
                text=text,
                message_type=message_type,
                reply_to=reply_to,
            )
            ChatRoom.objects.filter(pk=chat.pk).update(
                last_message=message,
                updated_at=timezone.now(),
            )
            ChatParticipant.objects.filter(chat=chat, user=sender).update(
                last_read_message=message,
                updated_at=timezone.now(),
            )
        return message

    @staticmethod
    def create_official_warning_message(
        target,
        report,
        moderator_note: str = "",
        *,
        warning_context: str = "chat",
    ):
        chat, _ = ChatRoom.objects.get_or_create(
            direct_key=f"school_admin_{target.pk}",
            defaults={
                "type": ChatRoom.TypeChoices.DIRECT,
                "title": "School Administration",
                "is_read_only": True,
            },
        )
        fields_to_update = []
        if chat.is_deleted:
            chat.is_deleted = False
            fields_to_update.append("is_deleted")
        if not chat.is_read_only:
            chat.is_read_only = True
            fields_to_update.append("is_read_only")
        if chat.title != "School Administration":
            chat.title = "School Administration"
            fields_to_update.append("title")
        if fields_to_update:
            fields_to_update.append("updated_at")
            chat.save(update_fields=fields_to_update)

        participant, participant_created = ChatParticipant.objects.update_or_create(
            chat=chat,
            user=target,
            defaults={
                "role": ChatParticipant.RoleChoices.MEMBER,
                "left_at": None,
            },
        )

        note_section = (
            f"\n\nModerator's note:\n{moderator_note.strip()}" if moderator_note.strip() else ""
        )
        if warning_context == "account":
            reviewed_activity = (
                "The School Administration has reviewed a complaint concerning your account "
                "and determined that the reported activity does not comply with our platform "
                "standards."
            )
            consequence = (
                "Repeated violations may result in temporary or permanent restriction of access "
                "to the platform."
            )
        else:
            reviewed_activity = (
                "The School Administration has reviewed a report concerning your recent activity "
                "in the platform chat and determined that the reported message does not comply "
                "with our standards of respectful and appropriate communication."
            )
            consequence = (
                "Repeated violations may result in temporary or permanent restriction of access "
                "to chat features."
            )

        warning_text = (
            "OFFICIAL WARNING FROM THE SCHOOL ADMINISTRATION\n\n"
            f"{reviewed_activity}\n\n"
            f"Reason: {report.get_reason_display()}"
            f"{note_section}\n\n"
            "Please refrain from repeating this behavior. All users are expected to communicate "
            "respectfully and must not post abusive, threatening, discriminatory, misleading, "
            "unsolicited, or otherwise inappropriate content. "
            f"{consequence}\n\n"
            "If you believe this warning was issued in error, please contact the School "
            "Administration through the support channel.\n\n"
            "This is an automated read-only notification. Replies are not accepted."
        )
        message = Message.objects.create(
            chat=chat,
            sender=None,
            text=warning_text,
            message_type=Message.TypeChoices.SYSTEM,
        )
        ChatRoom.objects.filter(pk=chat.pk).update(
            last_message=message,
            updated_at=timezone.now(),
        )
        return chat, participant, participant_created, message

    @staticmethod
    def update_message(message: Message, user, text: str) -> Message:
        if message.sender_id != user.pk:
            raise PermissionDenied("Only the sender can edit this message.")
        if message.is_deleted:
            raise ValidationError("Deleted messages cannot be edited.")
        message.text = text
        message.edited_at = timezone.now()
        message.save(update_fields=["text", "edited_at"])
        return message

    @staticmethod
    def delete_message(message: Message, user) -> Message:
        if message.sender_id != user.pk:
            raise PermissionDenied("Only the sender can delete this message.")
        if not message.is_deleted:
            message.is_deleted = True
            message.deleted_at = timezone.now()
            message.save(update_fields=["is_deleted", "deleted_at"])
        return message

    @staticmethod
    def mark_read(chat: ChatRoom, user, message: Message | None = None) -> ChatParticipant:
        participation = ChatService.get_active_participation(user, chat.pk)
        if message is None:
            message = chat.last_message
        if message is not None and message.chat_id != chat.pk:
            raise ValidationError({"message_id": "Message must belong to this chat."})
        participation.last_read_message = message
        participation.save(update_fields=["last_read_message", "updated_at"])
        return participation

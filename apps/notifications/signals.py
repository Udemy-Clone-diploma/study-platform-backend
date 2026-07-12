from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.chat.models import ChatParticipant, ChatRoom, Message
from apps.courses.models import Course
from apps.curriculum.models import Lesson
from apps.enrollments.models import Enrollment
from apps.homework.models import HomeworkSubmission
from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.users.models import User


CHAT_LINK_BY_ROLE = {
    User.RoleChoices.STUDENT: "/student-dashboard/chats",
    User.RoleChoices.TEACHER: "/teacher-dashboard/chats",
    User.RoleChoices.MODERATOR: "/moderator-dashboard/chats",
}

HOMEWORK_LINK_BY_ROLE = {
    User.RoleChoices.STUDENT: "/student-dashboard/homework",
    User.RoleChoices.TEACHER: "/teacher-dashboard/homework",
}


def _display_name(user: User | None) -> str:
    if user is None:
        return "Someone"
    return user.get_full_name() or user.email


def _truncate(value: str, limit: int = 180) -> str:
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1]}..."


def _chat_notification_title(message: Message) -> str:
    sender_name = _display_name(message.sender)
    if message.chat.type == ChatRoom.TypeChoices.GROUP:
        chat_title = message.chat.title or "group chat"
        return _truncate(f"New message in {chat_title}", 255)
    return _truncate(f"New message from {sender_name}", 255)


def _chat_notification_body(message: Message) -> str:
    sender_name = _display_name(message.sender)
    text = message.text or "Sent an attachment."
    if message.chat.type == ChatRoom.TypeChoices.GROUP:
        return _truncate(f"{sender_name}: {text}", 512)
    return _truncate(text, 512)


@receiver(post_save, sender=Lesson)
def lesson_created(sender, instance: Lesson, created: bool, **kwargs):
    """Fan a `new_lesson` notification out to every student with active access.

    There is no separate publish step on lessons; a lesson becoming available
    is its creation inside a published course, so that is the trigger.
    """
    if not created:
        return

    course = instance.module.course
    if course.status != Course.StatusChoices.PUBLISHED:
        return

    recipient_ids = (
        Enrollment.objects.with_active_access()
        .filter(course_id=course.id)
        .values_list("student_profile__user_id", flat=True)
    )
    recipients = list(User.objects.filter(id__in=list(recipient_ids)))

    NotificationService.fan_out(
        recipients=recipients,
        type=Notification.TypeChoices.NEW_LESSON,
        title=course.title,
        body=f"New lesson published: {instance.title}",
        link_url=f"/learn/{course.slug}/{instance.id}",
        payload={
            "course_slug": course.slug,
            "lesson_id": instance.id,
            "module_id": instance.module_id,
        },
    )


@receiver(post_save, sender=Message)
def chat_message_created(sender, instance: Message, created: bool, **kwargs):
    if not created or instance.is_deleted:
        return

    message = (
        Message.objects.select_related("chat", "sender")
        .filter(pk=instance.pk, chat__is_deleted=False)
        .first()
    )
    if message is None or message.message_type == Message.TypeChoices.SYSTEM:
        return

    participants = (
        ChatParticipant.objects.filter(
            chat_id=message.chat_id,
            left_at__isnull=True,
            is_muted=False,
            user__is_deleted=False,
        )
        .exclude(user_id=message.sender_id)
        .select_related("user")
    )

    for participant in participants:
        NotificationService.create(
            recipient=participant.user,
            type=Notification.TypeChoices.NEW_MESSAGE,
            title=_chat_notification_title(message),
            body=_chat_notification_body(message),
            link_url=CHAT_LINK_BY_ROLE.get(participant.user.role),
            actor=message.sender,
            payload={
                "chat_id": message.chat_id,
                "message_id": message.id,
                "sender_id": message.sender_id,
            },
        )


@receiver(pre_save, sender=HomeworkSubmission)
def homework_submission_remember_status(sender, instance: HomeworkSubmission, **kwargs):
    if instance.pk is None:
        instance._previous_status = None
        return
    instance._previous_status = (
        HomeworkSubmission.objects.filter(pk=instance.pk)
        .values_list("status", flat=True)
        .first()
    )


@receiver(post_save, sender=HomeworkSubmission)
def homework_submission_status_changed(
    sender,
    instance: HomeworkSubmission,
    created: bool,
    **kwargs,
):
    previous_status = getattr(instance, "_previous_status", None)
    if not created and previous_status == instance.status:
        return

    submission = (
        HomeworkSubmission.objects.select_related(
            "assignment",
            "assignment__course",
            "assignment__created_by",
            "enrollment__student_profile__user",
        )
        .filter(pk=instance.pk)
        .first()
    )
    if submission is None:
        return

    assignment = submission.assignment
    student_user = submission.enrollment.student_profile.user
    teacher_user = assignment.created_by

    if submission.status == HomeworkSubmission.StatusChoices.SUBMITTED:
        NotificationService.create(
            recipient=teacher_user,
            type=Notification.TypeChoices.HOMEWORK_SUBMITTED,
            title="Homework submitted",
            body=_truncate(
                f"{_display_name(student_user)} submitted homework: {assignment.title}",
                512,
            ),
            link_url=HOMEWORK_LINK_BY_ROLE.get(teacher_user.role),
            actor=student_user,
            payload={
                "course_slug": assignment.course.slug,
                "assignment_id": assignment.id,
                "submission_id": submission.id,
                "student_id": student_user.id,
            },
        )
        return

    if submission.status == HomeworkSubmission.StatusChoices.REVIEWED:
        NotificationService.create(
            recipient=student_user,
            type=Notification.TypeChoices.HOMEWORK_GRADED,
            title="Homework returned",
            body=_truncate(f"Your homework was reviewed: {assignment.title}", 512),
            link_url=HOMEWORK_LINK_BY_ROLE.get(student_user.role),
            actor=teacher_user,
            payload={
                "course_slug": assignment.course.slug,
                "assignment_id": assignment.id,
                "submission_id": submission.id,
                "score": submission.score,
            },
        )

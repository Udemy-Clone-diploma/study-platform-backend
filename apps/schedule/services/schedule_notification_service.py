from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.users.models import User


def _link_for(recipient: User, event_date) -> str:
    prefix = "teacher" if recipient.role == User.RoleChoices.TEACHER else "student"
    return f"/{prefix}-dashboard/schedule?date={event_date.isoformat()}"


def _invitations_link_for(recipient: User) -> str:
    prefix = "teacher" if recipient.role == User.RoleChoices.TEACHER else "student"
    return f"/{prefix}-dashboard?tab=invitations"


def _fmt_time(t) -> str:
    return str(t)[:5]


class ScheduleNotificationService:
    """Notifies the affected side of a schedule change. Every method excludes `actor` from recipients."""

    @staticmethod
    def session_participants(session) -> list[User]:
        if session.slot_id:
            if not session.slot.booked_by_id:
                return []
            return [session.slot.booked_by.student_profile.user]

        if session.schedule_id:
            from apps.courses.models import CohortMember

            members = CohortMember.objects.filter(
                cohort=session.schedule.cohort
            ).select_related("enrollment__student_profile__user")
            return [m.enrollment.student_profile.user for m in members]

        if session.cohort_id:
            from apps.courses.models import CohortMember

            members = CohortMember.objects.filter(
                cohort=session.cohort
            ).select_related("enrollment__student_profile__user")
            return [m.enrollment.student_profile.user for m in members]

        if session.student_profile_id:
            return [session.student_profile.user]

        return []

    @staticmethod
    def session_teacher(session) -> User:
        if session.slot_id:
            return session.slot.delivery_format.course.teacher_profile.user
        if session.schedule_id:
            return session.schedule.cohort.course.teacher_profile.user
        return session.course.teacher_profile.user

    @staticmethod
    def _session_course_title(session) -> str:
        if session.slot_id:
            return session.slot.delivery_format.course.title
        if session.schedule_id:
            return session.schedule.cohort.course.title
        return session.course.title

    @classmethod
    def notify_session_cancelled(cls, session, actor: User) -> None:
        recipients = [u for u in cls.session_participants(session) if u.id != actor.id]
        title = cls._session_course_title(session)
        for recipient in recipients:
            NotificationService.create(
                recipient=recipient,
                type=Notification.TypeChoices.SCHEDULE_EVENT,
                title=title,
                body=f"Session on {session.date.isoformat()} at {_fmt_time(session.start_time)}–{_fmt_time(session.end_time)} was cancelled.",
                actor=actor,
                link_url=_link_for(recipient, session.date),
                payload={"action": "cancelled", "session_id": session.id},
            )

    @classmethod
    def notify_session_restored(cls, session, actor: User) -> None:
        recipients = [u for u in cls.session_participants(session) if u.id != actor.id]
        title = cls._session_course_title(session)
        for recipient in recipients:
            NotificationService.create(
                recipient=recipient,
                type=Notification.TypeChoices.SCHEDULE_EVENT,
                title=title,
                body=f"Session on {session.date.isoformat()} at {_fmt_time(session.start_time)}–{_fmt_time(session.end_time)} was restored.",
                actor=actor,
                link_url=_link_for(recipient, session.date),
                payload={"action": "restored", "session_id": session.id},
            )

    @classmethod
    def notify_session_rescheduled(cls, session, actor: User, old_date, old_start_time, old_end_time) -> None:
        recipients = [u for u in cls.session_participants(session) if u.id != actor.id]
        title = cls._session_course_title(session)
        body = (
            f"Session moved from {old_date.isoformat()} {_fmt_time(old_start_time)}–{_fmt_time(old_end_time)} "
            f"to {session.date.isoformat()} {_fmt_time(session.start_time)}–{_fmt_time(session.end_time)}."
        )
        for recipient in recipients:
            NotificationService.create(
                recipient=recipient,
                type=Notification.TypeChoices.SCHEDULE_EVENT,
                title=title,
                body=body,
                actor=actor,
                link_url=_link_for(recipient, session.date),
                payload={"action": "rescheduled", "session_id": session.id},
            )

    @classmethod
    def notify_extra_session_created(cls, session) -> None:
        recipients = cls.session_participants(session)
        title = cls._session_course_title(session)
        for recipient in recipients:
            NotificationService.create(
                recipient=recipient,
                type=Notification.TypeChoices.SCHEDULE_EVENT,
                title=title,
                body=f"You were added to an extra session on {session.date.isoformat()} at {_fmt_time(session.start_time)}–{_fmt_time(session.end_time)}.",
                link_url=_link_for(recipient, session.date),
                payload={"action": "extra_session", "session_id": session.id},
            )

    @staticmethod
    def notify_recurring_time_changed(
        participants: list[User], course_title: str, actor: User, day_label: str, new_start, new_end
    ) -> None:
        from datetime import date as _date

        for recipient in [u for u in participants if u.id != actor.id]:
            NotificationService.create(
                recipient=recipient,
                type=Notification.TypeChoices.SCHEDULE_EVENT,
                title=course_title,
                body=f"Your weekly {course_title} time changed to {day_label} {_fmt_time(new_start)}–{_fmt_time(new_end)}.",
                actor=actor,
                link_url=_link_for(recipient, _date.today()),
                payload={"action": "recurring_time_changed"},
            )

    @staticmethod
    def notify_recurring_cancelled(participants: list[User], course_title: str, actor: User) -> None:
        from datetime import date as _date

        for recipient in [u for u in participants if u.id != actor.id]:
            NotificationService.create(
                recipient=recipient,
                type=Notification.TypeChoices.SCHEDULE_EVENT,
                title=course_title,
                body=f"Your weekly {course_title} sessions were cancelled.",
                actor=actor,
                link_url=_link_for(recipient, _date.today()),
                payload={"action": "recurring_cancelled"},
            )

    @staticmethod
    def notify_event_invited(invitation, actor: User) -> None:
        event = invitation.event
        NotificationService.create(
            recipient=invitation.invitee,
            type=Notification.TypeChoices.SCHEDULE_EVENT,
            title=event.title,
            body=f"{actor.get_full_name() or actor.email} invited you to \"{event.title}\" on {event.date.isoformat()}.",
            actor=actor,
            link_url=_invitations_link_for(invitation.invitee),
            payload={"action": "invited", "event_id": event.id},
        )

    @staticmethod
    def notify_event_rescheduled(event, invitees: list[User], actor: User) -> None:
        for invitee in [u for u in invitees if u.id != actor.id]:
            NotificationService.create(
                recipient=invitee,
                type=Notification.TypeChoices.SCHEDULE_EVENT,
                title=event.title,
                body=f"\"{event.title}\" was moved to {event.date.isoformat()} {_fmt_time(event.start_time)}. Please reconfirm.",
                actor=actor,
                link_url=_invitations_link_for(invitee),
                payload={"action": "event_rescheduled", "event_id": event.id},
            )

    @staticmethod
    def notify_event_cancelled(event, invitees: list[User], actor: User) -> None:
        for invitee in [u for u in invitees if u.id != actor.id]:
            NotificationService.create(
                recipient=invitee,
                type=Notification.TypeChoices.SCHEDULE_EVENT,
                title=event.title,
                body=f"\"{event.title}\" on {event.date.isoformat()} was cancelled.",
                actor=actor,
                link_url=_link_for(invitee, event.date),
                payload={"action": "event_cancelled"},
            )

    @staticmethod
    def notify_invitation_responded(invitation) -> None:
        event = invitation.event
        if invitation.invitee_id == event.owner_id:
            return
        verb = "accepted" if invitation.status == invitation.Status.ACCEPTED else "declined"
        invitee_name = invitation.invitee.get_full_name() or invitation.invitee.email
        NotificationService.create(
            recipient=event.owner,
            type=Notification.TypeChoices.SCHEDULE_EVENT,
            title=event.title,
            body=f"{invitee_name} {verb} your invitation to \"{event.title}\".",
            actor=invitation.invitee,
            link_url=_link_for(event.owner, event.date),
            payload={"action": "invitation_responded", "event_id": event.id, "response": invitation.status},
        )

from django.db import models


class EventInvitation(models.Model):
    """
    Tracks a user's invitation to a PersonalEvent.

    pending  → visible in invitations tab, can accept/decline
    accepted → event appears in invitee's calendar
    declined → visible in invitations tab with declined badge; can flip to accepted before event time
    After event end time passes, pending/declined invitations are cleaned up.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"

    event = models.ForeignKey(
        "PersonalEvent",
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    invitee = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="event_invitations",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    responded_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "event_invitations"
        constraints = [
            models.UniqueConstraint(fields=["event", "invitee"], name="unique_event_invitation"),
        ]

    def __str__(self):
        return f"{self.invitee} → {self.event} ({self.status})"

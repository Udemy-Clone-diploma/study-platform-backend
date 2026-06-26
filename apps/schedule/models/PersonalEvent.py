from django.db import models


class PersonalEvent(models.Model):
    """
    A personal or shared calendar event created by any user.

    If invitees are added, it becomes a shared event with a meeting_link.
    Simple personal events (no invitees) are only visible to the owner.
    """

    owner = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="personal_events",
    )
    title      = models.CharField(max_length=255)
    date       = models.DateField()
    start_time = models.TimeField()
    end_time   = models.TimeField()
    meeting_link = models.URLField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "personal_events"
        ordering = ["date", "start_time"]

    def __str__(self):
        return f"{self.owner} – {self.title} ({self.date})"
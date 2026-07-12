from django.db import models

from apps.common.files import UUIDUploadTo

from .Lesson import Lesson


class LessonDocument(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="documents")
    file = models.FileField(upload_to=UUIDUploadTo("lessons/documents"))
    original_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    # Set only on a pending-edit draft course's documents: points back at the live
    # document this one was cloned from, so approval can merge changes in place.
    source_document = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="draft_copies",
    )

    class Meta:
        db_table = "lesson_documents"
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_document"],
                condition=models.Q(source_document__isnull=False),
                name="unique_source_document",
            ),
        ]

    def __str__(self):
        return self.original_name
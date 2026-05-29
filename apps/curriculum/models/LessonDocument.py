from django.db import models

from apps.common.files import UUIDUploadTo

from .Lesson import Lesson


class LessonDocument(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="documents")
    file = models.FileField(upload_to=UUIDUploadTo("lessons/documents"))
    original_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "lesson_documents"
        ordering = ["created_at"]

    def __str__(self):
        return self.original_name
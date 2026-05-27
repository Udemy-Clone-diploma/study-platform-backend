from django.db import models

from apps.common.managers import ActiveManager

from .Test import Test


class Question(models.Model):
    class TypeChoices(models.TextChoices):
        MULTIPLE_CHOICE = "multiple_choice", "Multiple Choice"
        TRUE_FALSE = "true_false", "True/False"
        SHORT_ANSWER = "short_answer", "Short Answer"

    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name="questions",
    )

    question_type = models.CharField(
        max_length=20,
        choices=TypeChoices.choices,
        default=TypeChoices.MULTIPLE_CHOICE,
    )
    text = models.TextField()
    options = models.JSONField(default=list, blank=True)
    correct_index = models.SmallIntegerField(null=True, blank=True)
    correct_bool = models.BooleanField(null=True, blank=True)
    sample_answer = models.TextField(blank=True, default="")

    order = models.PositiveSmallIntegerField()

    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "questions"
        ordering = ["order"]

    def __str__(self):
        return self.text[:80]

from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.common.managers import ActiveManager


class EnrollmentQuerySet(models.QuerySet):
    def with_active_access(self):
        now = timezone.now()
        return self.filter(access_status="active").filter(
            Q(access_until__isnull=True) | Q(access_until__gte=now)
        )

    def exclude_completed(self):
        """Excludes enrollments the student has already finished (has a CourseCompletion).

        Used where "currently, actively studying" matters (notification fan-out,
        deadlines, schedule participation) -- distinct from content access, which
        a finished student keeps via `with_active_access()`.
        """
        from apps.enrollments.models import CourseCompletion

        return self.exclude(
            models.Exists(
                CourseCompletion.objects.filter(
                    student_profile_id=models.OuterRef("student_profile_id"),
                    course_id=models.OuterRef("course_id"),
                )
            )
        )


class ActiveEnrollmentManager(ActiveManager.from_queryset(EnrollmentQuerySet)):
    pass


class AllEnrollmentManager(models.Manager.from_queryset(EnrollmentQuerySet)):
    pass


class Enrollment(models.Model):
    class AccessStatusChoices(models.TextChoices):
        ACTIVE = "active", "Active"
        PENDING = "pending", "Pending"
        EXPIRED = "expired", "Expired"
        REVOKED = "revoked", "Revoked"

    id = models.BigAutoField(primary_key=True, db_column="id_enrollments")

    student_profile = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="enrollments",
        db_column="id_student_profile",
    )

    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="enrollments",
        db_column="id_course",
    )

    delivery_format = models.ForeignKey(
        "courses.CourseDeliveryFormat",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enrollments",
    )

    order_id = models.PositiveBigIntegerField(
        db_column="id_order",
        null=True,
        blank=True,
    )

    access_status = models.CharField(
        max_length=20,
        choices=AccessStatusChoices.choices,
        default=AccessStatusChoices.ACTIVE,
    )

    access_granted_at = models.DateTimeField(default=timezone.now)

    access_until = models.DateTimeField(null=True, blank=True)

    lessons_completed_count = models.PositiveIntegerField(default=0)

    last_lesson = models.ForeignKey(
        "curriculum.Lesson",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    last_opened_at = models.DateTimeField(null=True, blank=True)

    is_deleted = models.BooleanField(default=False)

    objects = ActiveEnrollmentManager()
    all_objects = AllEnrollmentManager()

    class Meta:
        db_table = "enrollments"
        ordering = ["-access_granted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student_profile", "course"],
                name="unique_enrollment_per_student_course",
            ),
            models.CheckConstraint(
                condition=(
                    Q(access_until__isnull=True)
                    | Q(access_until__gte=models.F("access_granted_at"))
                ),
                name="enrollment_access_until_after_granted_at",
            ),
        ]

    @property
    def has_active_access(self) -> bool:
        if self.access_status != self.AccessStatusChoices.ACTIVE:
            return False
        if self.access_until is None:
            return True
        return self.access_until >= timezone.now()

    def activate(self) -> None:
        self.access_status = self.AccessStatusChoices.ACTIVE
        self.access_granted_at = timezone.now()
        self.save(update_fields=["access_status", "access_granted_at"])

    def revoke(self) -> None:
        self.access_status = self.AccessStatusChoices.REVOKED
        self.save(update_fields=["access_status"])

    def expire(self) -> None:
        self.access_status = self.AccessStatusChoices.EXPIRED
        self.save(update_fields=["access_status"])

    def __str__(self):
        return f"{self.student_profile.user.email} -> {self.course.title}"

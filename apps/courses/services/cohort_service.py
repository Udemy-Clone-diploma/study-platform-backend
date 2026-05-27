from django.db import transaction

from apps.courses.models import Cohort, Course


class CohortService:
    @staticmethod
    @transaction.atomic
    def create_for_course(course: Course, validated_data: dict) -> Cohort:
        return Cohort.objects.create(course=course, **validated_data)

    @staticmethod
    @transaction.atomic
    def update_cohort(cohort: Cohort, validated_data: dict) -> Cohort:
        for field, value in validated_data.items():
            setattr(cohort, field, value)
        cohort.save()
        return cohort

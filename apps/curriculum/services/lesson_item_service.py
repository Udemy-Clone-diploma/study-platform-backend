from django.db.models import Max

from apps.curriculum.exceptions import LessonAlreadyHasTestError
from apps.curriculum.models import Lesson, LessonItem


class LessonItemService:
    @staticmethod
    def assert_single_test(lesson: Lesson, exclude_pk: int | None = None) -> None:
        qs = LessonItem.objects.filter(lesson=lesson, item_type=LessonItem.ItemType.TEST)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        if qs.exists():
            raise LessonAlreadyHasTestError("This lesson already has a test item.")

    @classmethod
    def create_item(cls, lesson: Lesson, validated_data: dict) -> LessonItem:
        if validated_data.get("item_type") == LessonItem.ItemType.TEST:
            cls.assert_single_test(lesson)
        next_order = (
            LessonItem.objects.filter(lesson=lesson).aggregate(m=Max("order"))["m"] or 0
        ) + 1
        return LessonItem.objects.create(lesson=lesson, order=next_order, **validated_data)

    @staticmethod
    def soft_delete_item(item: LessonItem) -> None:
        item.is_deleted = True
        item.save(update_fields=["is_deleted"])

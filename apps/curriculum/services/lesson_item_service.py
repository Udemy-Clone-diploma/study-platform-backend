from django.db import transaction
from django.db.models import Max

from apps.curriculum.exceptions import InvalidReorderError, LessonAlreadyHasTestError
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

    @staticmethod
    @transaction.atomic
    def reorder_items(lesson: Lesson, item_ids: list[int]) -> list[LessonItem]:
        items = list(LessonItem.objects.filter(lesson=lesson))
        if sorted(item_ids) != sorted(i.id for i in items):
            raise InvalidReorderError("Submitted item ids must match the lesson's current items exactly.")
        by_id = {i.id: i for i in items}

        # The (lesson, order) unique constraint is checked per-statement (not
        # deferrable), so writing final positions directly can collide with
        # whatever currently holds that slot -- stage through an out-of-range
        # offset first, then assign final positions.
        offset = len(item_ids)
        for item in items:
            item.order += offset
            item.save(update_fields=["order"])

        ordered_items = []
        for index, item_id in enumerate(item_ids, start=1):
            item = by_id[item_id]
            item.order = index
            item.save(update_fields=["order"])
            ordered_items.append(item)
        return ordered_items

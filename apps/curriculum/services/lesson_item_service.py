from apps.curriculum.models import Lesson, LessonItem


class LessonItemService:
    @staticmethod
    def create_item(lesson: Lesson, validated_data: dict) -> LessonItem:
        order = LessonItem.objects.filter(lesson=lesson).count() + 1
        return LessonItem.objects.create(lesson=lesson, order=order, **validated_data)

    @staticmethod
    def soft_delete_item(item: LessonItem) -> None:
        item.is_deleted = True
        item.save(update_fields=["is_deleted"])

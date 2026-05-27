from apps.curriculum.models import Lesson, Module


class LessonService:
    @staticmethod
    def create_lesson(module: Module, validated_data: dict) -> Lesson:
        order = Lesson.objects.filter(module=module).count() + 1
        return Lesson.objects.create(module=module, order=order, **validated_data)

    @staticmethod
    def soft_delete_lesson(lesson: Lesson) -> None:
        lesson.is_deleted = True
        lesson.save(update_fields=["is_deleted"])

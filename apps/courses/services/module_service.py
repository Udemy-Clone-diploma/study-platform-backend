from apps.courses.models import Course, Module


class ModuleService:
    @staticmethod
    def create_module(course: Course, validated_data: dict) -> Module:
        order = Module.objects.filter(course=course).count() + 1
        return Module.objects.create(course=course, order=order, **validated_data)

    @staticmethod
    def soft_delete_module(module: Module) -> None:
        module.is_deleted = True
        module.save(update_fields=["is_deleted"])

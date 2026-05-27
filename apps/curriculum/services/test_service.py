from apps.curriculum.models import Module, Test


class TestService:
    @staticmethod
    def create_test(module: Module, validated_data: dict) -> Test:
        order = Test.objects.filter(module=module).count() + 1
        return Test.objects.create(module=module, order=order, **validated_data)

    @staticmethod
    def soft_delete_test(test: Test) -> None:
        test.is_deleted = True
        test.save(update_fields=["is_deleted"])

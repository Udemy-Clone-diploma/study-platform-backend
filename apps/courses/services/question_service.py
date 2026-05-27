from apps.courses.models import Question, Test


class QuestionService:
    @staticmethod
    def create_question(test: Test, validated_data: dict) -> Question:
        order = Question.objects.filter(test=test).count() + 1
        return Question.objects.create(test=test, order=order, **validated_data)

    @staticmethod
    def soft_delete_question(question: Question) -> None:
        question.is_deleted = True
        question.save(update_fields=["is_deleted"])

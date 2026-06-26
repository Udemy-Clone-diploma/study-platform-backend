from django.db import migrations


def backfill_correct_indices(apps, schema_editor):
    Question = apps.get_model("curriculum", "Question")
    for question in Question.objects.exclude(correct_index=None):
        question.correct_indices = [question.correct_index]
        question.save(update_fields=["correct_indices"])


def reverse_backfill(apps, schema_editor):
    Question = apps.get_model("curriculum", "Question")
    for question in Question.objects.exclude(correct_indices=[]):
        question.correct_index = question.correct_indices[0]
        question.save(update_fields=["correct_index"])


class Migration(migrations.Migration):
    dependencies = [
        ("curriculum", "0009_question_accepted_answers_question_correct_indices_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_correct_indices, reverse_backfill),
    ]

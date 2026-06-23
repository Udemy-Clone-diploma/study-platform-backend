from django.contrib import admin

from apps.homework.models import HomeworkAssignment


@admin.register(HomeworkAssignment)
class HomeworkAssignmentAdmin(admin.ModelAdmin):
    list_display = ["title", "course", "status", "due_at", "created_at"]
    list_filter = ["status", "course"]
    search_fields = ["title", "description", "course__title"]
    autocomplete_fields = ["course", "module", "lesson", "created_by"]

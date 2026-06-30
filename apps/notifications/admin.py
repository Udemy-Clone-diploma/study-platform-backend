from django.contrib import admin

from apps.notifications.models import Notification, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "recipient", "type", "title", "is_read", "created_at")
    list_filter = ("type", "is_read")
    search_fields = ("title", "body", "recipient__email")
    raw_id_fields = ("recipient", "actor")


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user",)
    raw_id_fields = ("user",)

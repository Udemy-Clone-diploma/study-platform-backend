from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import ModeratorProfile, StudentProfile, TeacherProfile, User


def _is_moderator_profile_user_autocomplete(request):
    return (
        request.GET.get("app_label") == ModeratorProfile._meta.app_label
        and request.GET.get("model_name") == ModeratorProfile._meta.model_name
        and request.GET.get("field_name") == "user"
    )


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("-date_joined",)
    list_display = ("email", "first_name", "last_name", "role", "is_active", "is_staff", "date_joined")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("email", "first_name", "last_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        ("Role & permissions", {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "first_name", "last_name", "role", "password1", "password2"),
        }),
    )

    def get_search_results(self, request, queryset, search_term):
        queryset, may_have_duplicates = super().get_search_results(
            request,
            queryset,
            search_term,
        )
        if _is_moderator_profile_user_autocomplete(request):
            queryset = queryset.filter(
                role=User.RoleChoices.MODERATOR,
                moderator_profile__isnull=True,
            )
        return queryset, may_have_duplicates


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("user_email", "user_full_name")
    search_fields = ("user__email", "user__first_name", "user__last_name")
    list_select_related = ("user",)
    raw_id_fields = ("user",)

    @admin.display(description="Email", ordering="user__email")
    def user_email(self, obj):
        return obj.user.email

    @admin.display(description="Name")
    def user_full_name(self, obj):
        return obj.user.get_full_name()


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ("user_email", "user_full_name", "course_count")
    search_fields = ("user__email", "user__first_name", "user__last_name")
    list_select_related = ("user",)
    raw_id_fields = ("user",)

    @admin.display(description="Email", ordering="user__email")
    def user_email(self, obj):
        return obj.user.email

    @admin.display(description="Name")
    def user_full_name(self, obj):
        return obj.user.get_full_name()

    @admin.display(description="Courses")
    def course_count(self, obj):
        return obj.courses.count()


@admin.register(ModeratorProfile)
class ModeratorProfileAdmin(admin.ModelAdmin):
    list_display = ("user_email", "user_full_name", "level")
    search_fields = ("user__email", "user__first_name", "user__last_name")
    list_filter = ("level",)
    list_select_related = ("user",)
    autocomplete_fields = ("user",)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user":
            kwargs["queryset"] = User.objects.filter(
                role=User.RoleChoices.MODERATOR,
            ).order_by("email")
            kwargs["help_text"] = (
                "Start typing an email, first name, or last name. "
                "Only users with the moderator role can be selected."
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description="Email", ordering="user__email")
    def user_email(self, obj):
        return obj.user.email

    @admin.display(description="Name")
    def user_full_name(self, obj):
        return obj.user.get_full_name()

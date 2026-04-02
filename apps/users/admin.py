from django.contrib import admin

from .models import ModeratorProfile, StudentProfile, TeacherProfile, User

admin.site.register(User)
admin.site.register(StudentProfile)
admin.site.register(TeacherProfile)
admin.site.register(ModeratorProfile)

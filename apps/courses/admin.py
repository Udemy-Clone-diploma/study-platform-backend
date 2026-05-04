from django.contrib import admin

from .models import Category, Course, Tag

admin.site.register(Tag)
admin.site.register(Category)
admin.site.register(Course)

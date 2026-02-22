from django.contrib import admin
from .models import Project, SourceFile, Lesson, LessonSource

admin.site.register(Project)
admin.site.register(SourceFile)
admin.site.register(Lesson)
admin.site.register(LessonSource)

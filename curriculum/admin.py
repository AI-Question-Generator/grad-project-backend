from django.contrib import admin
from .models import Project, SourceFile, Lesson, LessonSource


class LessonInline(admin.TabularInline):
    model = Lesson
    fields = ('title', 'domain', 'unit_number', 'section', 'order')
    extra = 0
    show_change_link = True


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'is_default', 'created_at')
    list_filter = ('is_default',)
    search_fields = ('name', 'description')
    inlines = [LessonInline]


admin.site.register(SourceFile)


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'domain', 'unit_number', 'section', 'order', 'created_at')
    list_filter = ('project', 'domain', 'unit_number', 'section')
    search_fields = ('title', 'description', 'project__name')
    ordering = ('project', 'unit_number', 'section', 'order')


admin.site.register(LessonSource)

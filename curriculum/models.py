import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='projects')

    def __str__(self):
        return self.name


class SourceFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='source_files')
    file = models.FileField(upload_to='source_files/%Y/%m/', blank=True, null=True)
    file_hash = models.CharField(max_length=255)
    file_url = models.URLField(max_length=1024, blank=True)
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=50)
    file_size = models.PositiveIntegerField(default=0)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']
        constraints = [
            models.UniqueConstraint(fields=['owner', 'file_hash'], name='unique_owner_file_hash'),
        ]

    def __str__(self):
        return self.file_name

    def delete(self, *args, **kwargs):
        """Delete physical file when record is deleted"""
        if self.file:
            self.file.delete(save=False)
        super().delete(*args, **kwargs)


class Lesson(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class LessonSource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='sources')
    source_file = models.ForeignKey(SourceFile, on_delete=models.CASCADE, related_name='lesson_sources')
    start_page = models.PositiveIntegerField(default=1)
    end_page = models.PositiveIntegerField(default=1)
    extraction_config = models.JSONField(default=dict, blank=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.source_file.file_name} for {self.lesson.title}"

    def clean(self):
        if self.start_page > self.end_page:
            raise ValidationError('start_page must be less than or equal to end_page.')
        if self.source_file_id and self.source_file.page_count:
            if self.end_page > self.source_file.page_count:
                raise ValidationError(
                    f'end_page cannot exceed source file page count ({self.source_file.page_count}).'
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

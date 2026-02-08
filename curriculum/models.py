from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()

class CourseFile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='uploads/%Y/%m/%d/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.file.name} (by {self.user.username})"

class Lesson(models.Model):
    file = models.ForeignKey(CourseFile, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=255)
    content_text = models.TextField()
    lesson_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.lesson_id})"

import uuid

from django.conf import settings
from django.db import models
from curriculum.models import Lesson, Project

User = settings.AUTH_USER_MODEL


class QuestionType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class GenerationRequest(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='generation_requests')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='generation_requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_log = models.TextField(null=True, blank=True)
    lessons = models.ManyToManyField(Lesson, related_name='generation_requests', blank=True)
    question_types = models.ManyToManyField(QuestionType, related_name='generation_requests', blank=True)

    def __str__(self):
        return f"Request {self.id} for Project {self.project.name} - {self.status}"


class GeneratedQuestion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='generated_questions')
    generation_request = models.ForeignKey(
        GenerationRequest,
        on_delete=models.CASCADE,
        related_name='generated_questions',
        null=True,
        blank=True,
    )
    question_type = models.ForeignKey(
        QuestionType,
        on_delete=models.PROTECT,
        related_name='generated_questions',
    )
    content = models.TextField()
    correct_answer = models.TextField()
    distractors = models.JSONField(default=list)
    explanation = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    chunk_hash = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.question_type.code}: {self.content[:50]}..."

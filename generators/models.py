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
        ('COMPLETED_WITH_ERRORS', 'Completed with errors'),
        ('FAILED', 'Failed'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='generation_requests')
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='generation_requests',
        null=True, blank=True,
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING')
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_log = models.TextField(null=True, blank=True)

    # Lessons included in this generation request.
    lessons = models.ManyToManyField(Lesson, related_name='generation_requests', blank=True)

    def __str__(self):
        project_name = self.project.name if self.project else 'No project'
        return f"Request {self.id} for Project {project_name} - {self.status}"


class GenerationRequestQuestionConfig(models.Model):
    """
    Per-lesson, per-question-type configuration for a GenerationRequest.
    Lets the frontend ask for, e.g., 3 MCQs + 2 True/False for lesson A,
    and a different mix for lesson B, all within the same request.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    generation_request = models.ForeignKey(
        GenerationRequest,
        on_delete=models.CASCADE,
        related_name='question_configs',
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='generation_question_configs',
    )
    question_type = models.ForeignKey(
        QuestionType,
        on_delete=models.PROTECT,
        related_name='generation_question_configs',
    )
    num_questions = models.PositiveSmallIntegerField()

    class Meta:
        unique_together = ('generation_request', 'lesson', 'question_type')

    def __str__(self):
        return f"{self.generation_request_id} | {self.lesson_id} | {self.question_type.code} x{self.num_questions}"


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
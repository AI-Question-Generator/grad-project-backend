import uuid
from django.db import models
from curriculum.models import Lesson

class GenerationRequest(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_log = models.TextField(null=True, blank=True)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='generation_requests')

    def __str__(self):
        return f"Request {self.id} for Lesson {self.lesson.title} - {self.status}"

class GeneratedQuestion(models.Model):
    TYPE_CHOICES = (
        ('mcq', 'Multiple Choice'),
        ('tf', 'True/False'),
        ('short_answer', 'Short Answer'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='generated_questions')
    generation_request = models.ForeignKey(GenerationRequest, on_delete=models.CASCADE, related_name='generated_questions', null=True, blank=True)
    question_type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    content = models.TextField()
    correct_answer = models.TextField()
    distractors = models.JSONField(default=list)
    explanation = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    chunk_hash = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.question_type}: {self.content[:50]}..."

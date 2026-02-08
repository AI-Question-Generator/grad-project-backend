from django.db import models
from curriculum.models import Lesson

class GenerationRequest(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Completed', 'Completed'),
        ('Failed', 'Failed'),
    )
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='generation_requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)

class Question(models.Model):
    TYPE_CHOICES = (
        ('mcq', 'Video Multiple Choice'),
        ('tf', 'True/False'),
        ('short_answer', 'Short Answer'),
    )
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='questions')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    statement = models.TextField()
    explanation = models.TextField()
    correct_answer = models.TextField()
    distractors = models.JSONField(default=list)  # Stores list of strings

    def __str__(self):
        return f"{self.type}: {self.statement[:50]}..."

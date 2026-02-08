from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    TEACHER = 'teacher'
    STUDENT = 'student'
    ADMIN = 'admin'
    
    ROLE_CHOICES = (
        (TEACHER, 'Teacher'),
        (STUDENT, 'Student'),
        (ADMIN, 'Admin'),
    )
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=STUDENT)

    def __str__(self):
        return f"{self.username} ({self.role})"

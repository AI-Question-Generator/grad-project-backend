from django.contrib import admin
from .models import GenerationRequest, GeneratedQuestion, QuestionType

admin.site.register(QuestionType)
admin.site.register(GenerationRequest)
admin.site.register(GeneratedQuestion)

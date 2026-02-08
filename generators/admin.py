from django.contrib import admin
from .models import GenerationRequest, Question

admin.site.register(GenerationRequest)
admin.site.register(Question)

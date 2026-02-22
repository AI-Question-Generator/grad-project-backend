from django.contrib import admin
from .models import GenerationRequest, GeneratedQuestion

admin.site.register(GenerationRequest)
admin.site.register(GeneratedQuestion)

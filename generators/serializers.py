from rest_framework import serializers
from .models import GenerationRequest, GeneratedQuestion

class GenerationRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = GenerationRequest
        fields = '__all__'
        read_only_fields = ['id', 'status', 'requested_at', 'completed_at', 'error_log']

class GeneratedQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedQuestion
        fields = '__all__'
        read_only_fields = ['id', 'created_at']

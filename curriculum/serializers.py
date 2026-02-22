from rest_framework import serializers
from .models import Project, SourceFile, Lesson, LessonSource

class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'owner']

class SourceFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = SourceFile
        fields = '__all__'
        read_only_fields = ['id', 'uploaded_at', 'owner']

class LessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = '__all__'
        read_only_fields = ['id', 'created_at']

class LessonSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonSource
        fields = '__all__'
        read_only_fields = ['id']

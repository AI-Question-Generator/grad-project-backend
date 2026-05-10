from rest_framework import serializers
from .models import Project, SourceFile, Lesson, LessonSource


# ─── Write serializers (unchanged, backward-compatible) ─────────────────────

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


# ─── Read serializers (new, frontend-optimized) ─────────────────────────────

class LessonSummarySerializer(serializers.ModelSerializer):
    """Lightweight lesson representation nested inside project responses."""
    name = serializers.CharField(source='title', read_only=True)
    sourceCount = serializers.IntegerField(source='source_count', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = Lesson
        fields = ['id', 'name', 'description', 'sourceCount', 'createdAt']


class ProjectResponseSerializer(serializers.ModelSerializer):
    """Rich project serializer for list and detail read operations."""
    isDefault = serializers.BooleanField(source='is_default', read_only=True)
    lessonCount = serializers.IntegerField(source='lesson_count', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    lessons = LessonSummarySerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = ['id', 'name', 'description', 'isDefault', 'lessonCount', 'createdAt', 'lessons']

from rest_framework import serializers
from .models import CourseFile, Lesson

class CourseFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseFile
        fields = ['id', 'user', 'file', 'uploaded_at']
        read_only_fields = ['user', 'uploaded_at']

class LessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = ['id', 'file', 'title', 'content_text', 'lesson_id', 'created_at']
        read_only_fields = ['lesson_id', 'created_at']

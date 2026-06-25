from rest_framework import serializers

from curriculum.models import Lesson, Project
from .models import GenerationRequest, GeneratedQuestion, QuestionType


class QuestionTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionType
        fields = ['id', 'code', 'name', 'is_active']
        read_only_fields = fields


class GeneratedQuestionSerializer(serializers.ModelSerializer):
    questionType = serializers.CharField(source='question_type.code', read_only=True)
    questionTypeId = serializers.UUIDField(source='question_type_id', read_only=True)
    lessonId = serializers.UUIDField(source='lesson_id', read_only=True)
    generationRequestId = serializers.UUIDField(source='generation_request_id', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = GeneratedQuestion
        fields = [
            'id',
            'lessonId',
            'generationRequestId',
            'questionType',
            'questionTypeId',
            'content',
            'correct_answer',
            'distractors',
            'explanation',
            'createdAt',
            'chunk_hash',
        ]
        read_only_fields = fields


class GenerationRequestCreateSerializer(serializers.Serializer):
    project = serializers.UUIDField()
    lesson_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    question_type_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)

    def validate(self, attrs):
        request = self.context['request']
        user = request.user

        try:
            project = Project.objects.get(id=attrs['project'], owner=user)
        except Project.DoesNotExist as exc:
            raise serializers.ValidationError({'project': 'Project not found or not owned by you.'}) from exc

        lessons = Lesson.objects.filter(id__in=attrs['lesson_ids'], project=project)
        if lessons.count() != len(set(attrs['lesson_ids'])):
            raise serializers.ValidationError({'lesson_ids': 'One or more lessons do not belong to this project.'})

        question_types = QuestionType.objects.filter(id__in=attrs['question_type_ids'], is_active=True)
        if question_types.count() != len(set(attrs['question_type_ids'])):
            raise serializers.ValidationError({'question_type_ids': 'One or more question types are invalid.'})

        attrs['project_obj'] = project
        attrs['lessons'] = list(lessons)
        attrs['question_types'] = list(question_types)
        return attrs

    def create(self, validated_data):
        generation_request = GenerationRequest.objects.create(
            user=self.context['request'].user,
            project=validated_data['project_obj'],
        )
        generation_request.lessons.set(validated_data['lessons'])
        generation_request.question_types.set(validated_data['question_types'])
        return generation_request


class GenerationRequestResponseSerializer(serializers.ModelSerializer):
    projectId = serializers.UUIDField(source='project_id', read_only=True)
    projectName = serializers.CharField(source='project.name', read_only=True)
    userId = serializers.IntegerField(source='user_id', read_only=True)
    requestedAt = serializers.DateTimeField(source='requested_at', read_only=True)
    completedAt = serializers.DateTimeField(source='completed_at', read_only=True)
    errorLog = serializers.CharField(source='error_log', read_only=True)
    lessonIds = serializers.SerializerMethodField()
    questionTypeIds = serializers.SerializerMethodField()
    generatedQuestions = GeneratedQuestionSerializer(source='generated_questions', many=True, read_only=True)

    class Meta:
        model = GenerationRequest
        fields = [
            'id',
            'status',
            'projectId',
            'projectName',
            'userId',
            'requestedAt',
            'completedAt',
            'errorLog',
            'lessonIds',
            'questionTypeIds',
            'generatedQuestions',
        ]
        read_only_fields = fields

    def get_lessonIds(self, obj):
        return [str(lesson_id) for lesson_id in obj.lessons.values_list('id', flat=True)]

    def get_questionTypeIds(self, obj):
        return [str(type_id) for type_id in obj.question_types.values_list('id', flat=True)]

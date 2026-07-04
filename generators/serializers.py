from rest_framework import serializers
from django.db.models import Q

from curriculum.models import Lesson, Project
from .models import (
    GenerationRequest,
    GenerationRequestQuestionConfig,
    GeneratedQuestion,
    QuestionType,
)


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


# ---------------------------------------------------------------------------
# Create-side serializers (frontend -> backend)
# ---------------------------------------------------------------------------

class LessonQuestionTypeRequestSerializer(serializers.Serializer):
    """One question-type request within a lesson's config, e.g. {mcq: 3}."""
    question_type_id = serializers.UUIDField()
    num_questions = serializers.IntegerField(min_value=1, max_value=20)


class LessonGenerationConfigSerializer(serializers.Serializer):
    """A single lesson plus the mix of question types/counts requested for it."""
    lesson_id = serializers.UUIDField()
    question_types = LessonQuestionTypeRequestSerializer(many=True, allow_empty=False)

    def validate_question_types(self, value):
        type_ids = [qt['question_type_id'] for qt in value]
        if len(type_ids) != len(set(type_ids)):
            raise serializers.ValidationError('Duplicate question_type_id for the same lesson.')
        return value


class GenerationRequestCreateSerializer(serializers.Serializer):
    """
    Frontend payload shape:
    {
        "project": "<uuid>",
            {
                "lesson_id": "<uuid>",
                "question_types": [
                    {"question_type_id": "<uuid>", "num_questions": 3},
                    {"question_type_id": "<uuid>", "num_questions": 2}
                ]
            },
            ...
        ]
    }
    """
    project = serializers.UUIDField()
    lessons = LessonGenerationConfigSerializer(many=True, allow_empty=False)

    def validate(self, attrs):
        request = self.context['request']
        user = request.user

        project = Project.objects.filter(
            Q(id=attrs['project'], owner=user) | Q(id=attrs['project'], is_default=True)
        ).first()
        # project may be None here - that's fine, we still proceed with
        # the rest of the flow and just store project as null.

        lesson_payloads = attrs['lessons']
        lesson_ids = [lp['lesson_id'] for lp in lesson_payloads]
        if len(lesson_ids) != len(set(lesson_ids)):
            raise serializers.ValidationError({'lessons': 'Duplicate lesson_id in request.'})

        if project is not None:
            lessons_qs = Lesson.objects.filter(id__in=lesson_ids, project=project)
        else:
            # No valid project to scope by - fall back to any lesson the
            # user can access through one of their own or default projects.
            lessons_qs = Lesson.objects.filter(
                Q(id__in=lesson_ids, project__owner=user) | Q(id__in=lesson_ids, project__is_default=True)
            )

        lessons_map = {lesson.id: lesson for lesson in lessons_qs}
        if len(lessons_map) != len(set(lesson_ids)):
            raise serializers.ValidationError({'lessons': 'One or more lessons do not belong to this project.'})

        all_type_ids = {
            qt['question_type_id']
            for lp in lesson_payloads
            for qt in lp['question_types']
        }
        types_qs = QuestionType.objects.filter(id__in=all_type_ids, is_active=True)
        types_map = {qtype.id: qtype for qtype in types_qs}
        if len(types_map) != len(all_type_ids):
            raise serializers.ValidationError({'lessons': 'One or more question types are invalid or inactive.'})

        attrs['project_obj'] = project
        attrs['lessons_map'] = lessons_map
        attrs['types_map'] = types_map
        return attrs

    def create(self, validated_data):
        generation_request = GenerationRequest.objects.create(
            user=self.context['request'].user,
            project=validated_data['project_obj'],
        )

        lessons_map = validated_data['lessons_map']
        types_map = validated_data['types_map']
        lesson_payloads = validated_data['lessons']

        generation_request.lessons.set(lessons_map.values())

        configs = [
            GenerationRequestQuestionConfig(
                generation_request=generation_request,
                lesson=lessons_map[lp['lesson_id']],
                question_type=types_map[qt['question_type_id']],
                num_questions=qt['num_questions'],
            )
            for lp in lesson_payloads
            for qt in lp['question_types']
        ]
        GenerationRequestQuestionConfig.objects.bulk_create(configs)

        return generation_request


# ---------------------------------------------------------------------------
# Read-side serializers (backend -> frontend)
# ---------------------------------------------------------------------------

class GenerationRequestQuestionConfigSerializer(serializers.ModelSerializer):
    lessonId = serializers.UUIDField(source='lesson_id', read_only=True)
    questionTypeId = serializers.UUIDField(source='question_type_id', read_only=True)
    questionTypeCode = serializers.CharField(source='question_type.code', read_only=True)
    numQuestions = serializers.IntegerField(source='num_questions', read_only=True)

    class Meta:
        model = GenerationRequestQuestionConfig
        fields = ['id', 'lessonId', 'questionTypeId', 'questionTypeCode', 'numQuestions']
        read_only_fields = fields


class GenerationRequestResponseSerializer(serializers.ModelSerializer):
    projectId = serializers.SerializerMethodField()
    projectName = serializers.SerializerMethodField()
    userId = serializers.IntegerField(source='user_id', read_only=True)
    requestedAt = serializers.DateTimeField(source='requested_at', read_only=True)
    completedAt = serializers.DateTimeField(source='completed_at', read_only=True)
    errorLog = serializers.CharField(source='error_log', read_only=True)
    lessonIds = serializers.SerializerMethodField()
    questionConfigs = GenerationRequestQuestionConfigSerializer(
        source='question_configs', many=True, read_only=True
    )
    generatedQuestions = GeneratedQuestionSerializer(source='generated_questions', many=True, read_only=True)
    progress = serializers.SerializerMethodField()

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
            'questionConfigs',
            'generatedQuestions',
            'progress',
        ]
        read_only_fields = fields

    def get_lessonIds(self, obj):
        return [str(lesson_id) for lesson_id in obj.lessons.values_list('id', flat=True)]

    def get_projectId(self, obj):
        return str(obj.project_id) if obj.project_id else None

    def get_projectName(self, obj):
        return obj.project.name if obj.project else None

    def get_progress(self, obj):
        return compute_progress(obj)


class GenerationRequestStatusSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for polling. Omits questionConfigs and
    generatedQuestions so frequent polls stay cheap; the frontend should
    switch to GenerationRequestResponseSerializer's endpoint once status
    reaches a terminal state (COMPLETED / COMPLETED_WITH_ERRORS / FAILED).
    """
    errorLog = serializers.CharField(source='error_log', read_only=True)
    completedAt = serializers.DateTimeField(source='completed_at', read_only=True)
    progress = serializers.SerializerMethodField()

    class Meta:
        model = GenerationRequest
        fields = ['id', 'status', 'errorLog', 'completedAt', 'progress']
        read_only_fields = fields

    def get_progress(self, obj):
        return compute_progress(obj)


def compute_progress(obj):
    """
    Lightweight progress signal for frontend polling:
    how many (lesson, question_type) configs have produced at least
    one generated question, vs. how many were requested in total.
    """
    total_configs = obj.question_configs.count()
    if total_configs == 0:
        return {'requested': 0, 'fulfilled': 0}

    fulfilled = (
        obj.generated_questions
        .values('lesson_id', 'question_type_id')
        .distinct()
        .count()
    )
    return {'requested': total_configs, 'fulfilled': fulfilled}

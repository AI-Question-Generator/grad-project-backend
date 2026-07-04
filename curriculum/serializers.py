from django.db import transaction
from rest_framework import serializers

from .models import Project, SourceFile, Lesson, LessonSource


class LessonSourceWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonSource
        fields = ['source_file', 'start_page', 'end_page', 'order']

    def validate(self, attrs):
        start_page = attrs.get('start_page', 1)
        end_page = attrs.get('end_page', 1)
        if start_page > end_page:
            raise serializers.ValidationError('start_page must be less than or equal to end_page.')

        source_file = attrs.get('source_file')
        request = self.context.get('request')
        if source_file and request and source_file.owner_id != request.user.id:
            raise serializers.ValidationError('Source file does not belong to the current user.')

        if source_file and source_file.page_count and end_page > source_file.page_count:
            raise serializers.ValidationError(
                f'end_page cannot exceed source file page count ({source_file.page_count}).'
            )
        return attrs


class LessonWriteSerializer(serializers.ModelSerializer):
    sources = LessonSourceWriteSerializer(many=True, required=False, default=list)

    class Meta:
        model = Lesson
        fields = ['title', 'description', 'unit_number', 'section', 'order', 'sources']


class ProjectWriteSerializer(serializers.ModelSerializer):
    lessons = LessonWriteSerializer(many=True, required=False, default=list)

    class Meta:
        model = Project
        fields = ['name', 'description', 'is_default', 'lessons']
        read_only_fields = ['id', 'created_at', 'owner']

    def validate(self, attrs):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        is_default = attrs.get('is_default', getattr(self.instance, 'is_default', False))

        if self.instance and self.instance.is_default:
            raise serializers.ValidationError('Default projects are read-only.')

        if is_default and (user is None or getattr(user, 'role', None) != 'admin'):
            raise serializers.ValidationError('Only admins can create default projects.')

        return attrs

    def _create_lessons(self, project, lessons_data):
        for lesson_data in lessons_data:
            sources_data = lesson_data.pop('sources', [])
            lesson = Lesson.objects.create(project=project, **lesson_data)
            for source_data in sources_data:
                LessonSource.objects.create(lesson=lesson, **source_data)

    @transaction.atomic
    def create(self, validated_data):
        lessons_data = validated_data.pop('lessons', [])
        project = Project.objects.create(**validated_data)
        self._create_lessons(project, lessons_data)
        return project

    @transaction.atomic
    def update(self, instance, validated_data):
        lessons_data = validated_data.pop('lessons', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if lessons_data is not None:
            instance.lessons.all().delete()
            self._create_lessons(instance, lessons_data)

        return instance


class ProjectSerializer(serializers.ModelSerializer):
    """Backward-compatible flat project serializer."""

    class Meta:
        model = Project
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'owner']


class SourceFileUploadSerializer(serializers.Serializer):
    file = serializers.FileField(use_url=False)

    def validate_file(self, value):
        from .utils import validate_pdf_upload

        try:
            page_count = validate_pdf_upload(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc

        value.page_count = page_count
        return value


class SourceFileResponseSerializer(serializers.ModelSerializer):
    fileName = serializers.CharField(source='file_name', read_only=True)
    fileUrl = serializers.URLField(source='file_url', read_only=True)
    fileHash = serializers.CharField(source='file_hash', read_only=True)
    fileSize = serializers.IntegerField(source='file_size', read_only=True)
    pageCount = serializers.IntegerField(source='page_count', read_only=True)
    fileType = serializers.CharField(source='file_type', read_only=True)
    uploadedAt = serializers.DateTimeField(source='uploaded_at', read_only=True)

    class Meta:
        model = SourceFile
        fields = ['id', 'fileName', 'fileUrl', 'fileHash', 'fileSize', 'pageCount', 'fileType', 'uploadedAt']


class LessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = '__all__'
        read_only_fields = ['id', 'created_at']

    def validate(self, attrs):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        project = attrs.get('project') or getattr(self.instance, 'project', None)

        if project and project.is_default:
            raise serializers.ValidationError('Default projects are read-only.')

        if project and request and project.owner_id != user.id and getattr(user, 'role', None) != 'admin':
            raise serializers.ValidationError('Lesson does not belong to the current user.')

        return attrs


class LessonSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonSource
        fields = '__all__'
        read_only_fields = ['id']

    def validate(self, attrs):
        start_page = attrs.get('start_page', getattr(self.instance, 'start_page', 1))
        end_page = attrs.get('end_page', getattr(self.instance, 'end_page', 1))
        if start_page > end_page:
            raise serializers.ValidationError('start_page must be less than or equal to end_page.')

        source_file = attrs.get('source_file') or getattr(self.instance, 'source_file', None)
        lesson = attrs.get('lesson') or getattr(self.instance, 'lesson', None)
        request = self.context.get('request')

        if lesson and lesson.project.is_default:
            raise serializers.ValidationError('Default projects are read-only.')

        if source_file and request and source_file.owner_id != request.user.id:
            raise serializers.ValidationError('Source file does not belong to the current user.')

        if lesson and request and lesson.project.owner_id != request.user.id:
            raise serializers.ValidationError('Lesson does not belong to the current user.')

        if source_file and source_file.page_count and end_page > source_file.page_count:
            raise serializers.ValidationError(
                f'end_page cannot exceed source file page count ({source_file.page_count}).'
            )
        return attrs


class LessonSourceSummarySerializer(serializers.ModelSerializer):
    sourceFileId = serializers.UUIDField(source='source_file_id', read_only=True)
    fileName = serializers.CharField(source='source_file.file_name', read_only=True)
    fileUrl = serializers.URLField(source='source_file.file_url', read_only=True)
    startPage = serializers.IntegerField(source='start_page', read_only=True)
    endPage = serializers.IntegerField(source='end_page', read_only=True)
    order = serializers.IntegerField(read_only=True)

    class Meta:
        model = LessonSource
        fields = ['id', 'sourceFileId', 'fileName', 'fileUrl', 'startPage', 'endPage', 'order']


class LessonSummarySerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='title', read_only=True)
    unitNumber = serializers.IntegerField(source='unit_number', read_only=True)
    sourceCount = serializers.IntegerField(source='source_count', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    sources = LessonSourceSummarySerializer(many=True, read_only=True)
    section = serializers.CharField(read_only=True)
    order = serializers.IntegerField(read_only=True)

    class Meta:
        model = Lesson
        fields = [
            'id',
            'name',
            'description',
            'unitNumber',
            'section',
            'order',
            'sourceCount',
            'createdAt',
            'sources',
        ]


class ProjectResponseSerializer(serializers.ModelSerializer):
    isDefault = serializers.BooleanField(source='is_default', read_only=True)
    lessonCount = serializers.IntegerField(source='lesson_count', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    lessons = LessonSummarySerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = ['id', 'name', 'description', 'isDefault', 'lessonCount', 'createdAt', 'lessons']


class ProjectSetupStatusSerializer(serializers.ModelSerializer):
    setupStatus = serializers.CharField(source='ai_setup_status', read_only=True)
    setupFeedback = serializers.CharField(source='ai_setup_feedback', read_only=True)
    setupStartedAt = serializers.DateTimeField(source='ai_setup_started_at', read_only=True)
    setupCompletedAt = serializers.DateTimeField(source='ai_setup_completed_at', read_only=True)

    class Meta:
        model = Project
        fields = ['id', 'setupStatus', 'setupFeedback', 'setupStartedAt', 'setupCompletedAt']


class ProjectCreateResponseSerializer(ProjectResponseSerializer):
    setup = serializers.SerializerMethodField()

    class Meta(ProjectResponseSerializer.Meta):
        fields = ProjectResponseSerializer.Meta.fields + ['setup']

    def get_setup(self, obj):
        return ProjectSetupStatusSerializer(obj).data

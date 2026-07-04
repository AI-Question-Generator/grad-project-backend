import logging
import uuid

from django.db import transaction
from django.db.models import Count, Prefetch, Q
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied

from .models import Project, SourceFile, Lesson, LessonSource
from .serializers import (
    ProjectWriteSerializer,
    ProjectResponseSerializer,
    ProjectCreateResponseSerializer,
    ProjectSetupStatusSerializer,
    SourceFileUploadSerializer,
    SourceFileResponseSerializer,
    LessonSerializer,
    LessonSourceSerializer,
)
from .utils import compute_file_hash, build_file_url
from .tasks import setup_project_ai


logger = logging.getLogger(__name__)


class ProjectViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return ProjectResponseSerializer
        return ProjectWriteSerializer

    def get_queryset(self):
        return (
            Project.objects
            .filter(Q(owner=self.request.user) | Q(is_default=True))
            .annotate(lesson_count=Count('lessons'))
            .prefetch_related(
                Prefetch(
                    'lessons',
                    queryset=Lesson.objects.annotate(
                        source_count=Count('sources')
                    ).prefetch_related(
                        Prefetch(
                            'sources',
                            queryset=LessonSource.objects.select_related('source_file'),
                        )
                    ),
                )
            )
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer):
        project = serializer.save(owner=self.request.user)
        project.ai_setup_status = Project.SETUP_PENDING
        project.ai_setup_feedback = 'AI project setup queued.'
        project.save(update_fields=['ai_setup_status', 'ai_setup_feedback'])
        try:
            setup_project_ai.delay(str(project.id))
        except Exception:
            logger.exception(
                'Celery is unavailable; running AI setup synchronously for project %s',
                project.id,
            )
            setup_project_ai.apply(args=[str(project.id)])

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        project = serializer.instance
        response_serializer = ProjectCreateResponseSerializer(project, context=self.get_serializer_context())
        headers = self.get_success_headers(response_serializer.data)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_update(self, serializer):
        if serializer.instance.is_default:
            raise PermissionDenied('Default projects are read-only.')
        serializer.save()

    def perform_destroy(self, instance):
        if instance.is_default:
            raise PermissionDenied('Default projects are read-only.')
        instance.delete()

    @action(detail=False, methods=['post'], url_path='sync-ai')
    def sync_ai(self, request):
        if request.user.role != 'admin':
            raise PermissionDenied('Only admins can sync AI projects.')

        projects = request.data.get('projects', [])
        if not isinstance(projects, list) or not projects:
            return Response({'detail': 'projects must be a non-empty list.'}, status=status.HTTP_400_BAD_REQUEST)

        imported = []
        try:
            with transaction.atomic():
                for project_data in projects:
                    project_id = project_data.get('id') or project_data.get('project_id')
                    if not project_id:
                        return Response({'detail': 'Each project requires an id.'}, status=status.HTTP_400_BAD_REQUEST)

                    project, _ = Project.objects.update_or_create(
                        id=project_id,
                        defaults={
                            'name': project_data.get('name', str(project_id)),
                            'description': project_data.get('description', ''),
                            'is_default': project_data.get('is_default', True),
                            'owner': request.user,
                            'ai_setup_status': Project.SETUP_COMPLETED,
                            'ai_setup_feedback': 'Imported from the AI service.',
                        },
                    )

                    lessons = project_data.get('lessons', [])
                    if not isinstance(lessons, list):
                        raise ValueError('lessons must be a list.')

                    for index, lesson_payload in enumerate(lessons):
                        if not isinstance(lesson_payload, dict):
                            raise ValueError('Each lesson must be an object.')

                        title = lesson_payload.get('title') or lesson_payload.get('name')
                        if not title:
                            raise ValueError('Each lesson requires a title or name.')

                        lesson_id = lesson_payload.get('id') or lesson_payload.get('lesson_id')
                        lesson_data = {
                            'title': title,
                            'description': lesson_payload.get('description', ''),
                            'unit_number': lesson_payload.get('unit_number', lesson_payload.get('unitNumber')),
                            'section': lesson_payload.get('section', ''),
                            'order': lesson_payload.get('order', index),
                        }

                        if lesson_id:
                            try:
                                lesson_id = uuid.UUID(str(lesson_id))
                            except (TypeError, ValueError) as exc:
                                raise ValueError('Lesson ids must be valid UUIDs.') from exc
                            Lesson.objects.update_or_create(
                                id=lesson_id,
                                defaults={
                                    'project': project,
                                    **lesson_data,
                                },
                            )
                        else:
                            Lesson.objects.create(project=project, **lesson_data)

                    imported.append(str(project.id))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'imported': imported}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='setup-status')
    def setup_status(self, request, pk=None):
        project = self.get_object()
        serializer = ProjectSetupStatusSerializer(project)
        return Response(serializer.data)


class SourceFileViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']
    queryset = SourceFile.objects.all()

    def get_serializer_class(self):
        # FIX: Remove 'upload' from this list. 
        # This forces the action to return SourceFileUploadSerializer globally,
        # which allows Swagger to correctly map the multipart form-data request schema.
        if self.action in ('list', 'retrieve'):
            return SourceFileResponseSerializer
        return SourceFileUploadSerializer

    def get_queryset(self):
        return SourceFile.objects.filter(owner=self.request.user)

    @extend_schema(
        request=SourceFileUploadSerializer,
        responses={
            status.HTTP_200_OK: SourceFileResponseSerializer,
            status.HTTP_201_CREATED: SourceFileResponseSerializer,
        },
    )
    @action(
        detail=False,
        methods=['post'],
        url_path='upload',
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload(self, request):
        serializer = SourceFileUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_file = serializer.validated_data['file']
        file_hash = compute_file_hash(uploaded_file)

        existing = SourceFile.objects.filter(owner=request.user, file_hash=file_hash).first()
        if existing:
            response_serializer = SourceFileResponseSerializer(existing)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        # Your validation custom-injects page_count into the file object cleanly
        page_count = getattr(uploaded_file, 'page_count', None)
        
        source_file = SourceFile.objects.create(
            owner=request.user,
            file=uploaded_file,
            file_hash=file_hash,
            file_name=uploaded_file.name,
            file_type=uploaded_file.content_type or 'application/pdf',
            file_size=uploaded_file.size,
            page_count=page_count,
            file_url='',
        )
        source_file.file_url = build_file_url(request, source_file.file)
        source_file.save(update_fields=['file_url'])

        response_serializer = SourceFileResponseSerializer(source_file)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class LessonViewSet(viewsets.ModelViewSet):
    serializer_class = LessonSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Lesson.objects.filter(Q(project__owner=self.request.user) | Q(project__is_default=True))


class LessonSourceViewSet(viewsets.ModelViewSet):
    serializer_class = LessonSourceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_queryset(self):
        return LessonSource.objects.filter(
            Q(lesson__project__owner=self.request.user) | Q(lesson__project__is_default=True)
        )

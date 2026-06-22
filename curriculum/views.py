from django.db.models import Count, Prefetch
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Project, SourceFile, Lesson, LessonSource
from .serializers import (
    ProjectWriteSerializer,
    ProjectResponseSerializer,
    SourceFileSerializer,
    SourceFileUploadSerializer,
    SourceFileResponseSerializer,
    LessonSerializer,
    LessonSourceSerializer,
)
from .utils import compute_file_hash, build_file_url


class ProjectViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return ProjectResponseSerializer
        return ProjectWriteSerializer

    def get_queryset(self):
        return (
            Project.objects
            .filter(owner=self.request.user)
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
        serializer.save(owner=self.request.user)


class SourceFileViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve', 'upload'):
            return SourceFileResponseSerializer
        return SourceFileSerializer

    def get_queryset(self):
        return SourceFile.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=False, methods=['post'], url_path='upload')
    def upload(self, request):
        serializer = SourceFileUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_file = serializer.validated_data['file']
        file_hash = compute_file_hash(uploaded_file)

        existing = SourceFile.objects.filter(owner=request.user, file_hash=file_hash).first()
        if existing:
            response_serializer = SourceFileResponseSerializer(existing)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

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
        return Lesson.objects.filter(project__owner=self.request.user)


class LessonSourceViewSet(viewsets.ModelViewSet):
    serializer_class = LessonSourceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_queryset(self):
        return LessonSource.objects.filter(lesson__project__owner=self.request.user)

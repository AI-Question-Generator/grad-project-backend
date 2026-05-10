from rest_framework import viewsets, permissions
from django.db.models import Count, Prefetch
from .models import Project, SourceFile, Lesson, LessonSource
from .serializers import (
    ProjectSerializer,
    ProjectResponseSerializer,
    SourceFileSerializer,
    LessonSerializer,
    LessonSourceSerializer,
)


class ProjectViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return ProjectResponseSerializer
        return ProjectSerializer

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
                    ),
                )
            )
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class SourceFileViewSet(viewsets.ModelViewSet):
    serializer_class = SourceFileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SourceFile.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class LessonViewSet(viewsets.ModelViewSet):
    serializer_class = LessonSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Lesson.objects.filter(project__owner=self.request.user)


class LessonSourceViewSet(viewsets.ModelViewSet):
    serializer_class = LessonSourceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return LessonSource.objects.filter(lesson__project__owner=self.request.user)

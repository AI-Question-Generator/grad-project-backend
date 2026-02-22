from rest_framework import viewsets, permissions
from .models import Project, SourceFile, Lesson, LessonSource
from .serializers import ProjectSerializer, SourceFileSerializer, LessonSerializer, LessonSourceSerializer

class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Project.objects.filter(owner=self.request.user)

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

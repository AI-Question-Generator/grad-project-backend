from rest_framework import generics, permissions, parsers
from .models import CourseFile, Lesson
from .serializers import CourseFileSerializer, LessonSerializer

class FileUploadView(generics.CreateAPIView):
    queryset = CourseFile.objects.all()
    serializer_class = CourseFileSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class LessonCreateView(generics.CreateAPIView):
    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = [permissions.IsAuthenticated]

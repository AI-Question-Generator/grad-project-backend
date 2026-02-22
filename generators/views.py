from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import GenerationRequest, GeneratedQuestion
from .serializers import GenerationRequestSerializer, GeneratedQuestionSerializer
from curriculum.models import Lesson

from .tasks import process_generation_request

class GenerationRequestViewSet(viewsets.ModelViewSet):
    serializer_class = GenerationRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return GenerationRequest.objects.filter(lesson__project__owner=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        # Trigger Celery task
        process_generation_request.delay(serializer.instance.id)
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED, headers=headers)

class GeneratedQuestionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = GeneratedQuestionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return GeneratedQuestion.objects.filter(lesson__project__owner=self.request.user)

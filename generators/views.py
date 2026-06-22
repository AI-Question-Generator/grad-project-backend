from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response

from .models import GenerationRequest, GeneratedQuestion, QuestionType
from .serializers import (
    GenerationRequestCreateSerializer,
    GenerationRequestResponseSerializer,
    GeneratedQuestionSerializer,
    QuestionTypeSerializer,
)
from .tasks import process_generation_request


class QuestionTypeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = QuestionTypeSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = QuestionType.objects.filter(is_active=True)


class GenerationRequestViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'create':
            return GenerationRequestCreateSerializer
        return GenerationRequestResponseSerializer

    def get_queryset(self):
        return (
            GenerationRequest.objects
            .filter(user=self.request.user)
            .select_related('project', 'user')
            .prefetch_related('lessons', 'question_types', 'generated_questions__question_type')
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        generation_request = serializer.save()

        process_generation_request.delay(str(generation_request.id))

        response_serializer = GenerationRequestResponseSerializer(generation_request)
        return Response(response_serializer.data, status=status.HTTP_202_ACCEPTED)

    def destroy(self, request, *args, **kwargs):
        generation_request = self.get_object()
        if generation_request.status == 'PROCESSING':
            return Response(
                {'detail': 'Cannot delete a generation request while it is processing.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)


class GeneratedQuestionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = GeneratedQuestionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = GeneratedQuestion.objects.filter(
            lesson__project__owner=self.request.user
        ).select_related('question_type', 'lesson', 'generation_request')

        generation_request_id = self.request.query_params.get('generation_request')
        if generation_request_id:
            queryset = queryset.filter(generation_request_id=generation_request_id)

        return queryset

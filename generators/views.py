from django.utils import timezone
from rest_framework import viewsets, permissions, status as http_status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import GenerationRequest, GeneratedQuestion, QuestionType
from .serializers import (
    GenerationRequestCreateSerializer,
    GenerationRequestResponseSerializer,
    GenerationRequestStatusSerializer,
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
        if self.action == 'status':
            return GenerationRequestStatusSerializer
        return GenerationRequestResponseSerializer

    def get_queryset(self):
        queryset = (
            GenerationRequest.objects
            .filter(user=self.request.user)
            .select_related('project', 'user')
        )
        if self.action == 'status':
            # Lightweight queryset for frequent polling - no nested
            # question configs / generated questions prefetch needed.
            return queryset
        return queryset.prefetch_related(
            'lessons',
            'question_configs__lesson',
            'question_configs__question_type',
            'generated_questions__question_type',
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        generation_request = serializer.save()

        process_generation_request.delay(str(generation_request.id))

        response_serializer = GenerationRequestResponseSerializer(generation_request)
        return Response(response_serializer.data, status=http_status.HTTP_202_ACCEPTED)

    def destroy(self, request, *args, **kwargs):
        generation_request = self.get_object()
        if generation_request.status == 'PROCESSING':
            return Response(
                {'detail': 'Cannot delete a generation request while it is processing.'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """
        Lightweight endpoint for frontend polling.
        GET /generation-requests/{id}/status/

        Returns just id, status, errorLog, completedAt, and progress -
        without the heavier nested questionConfigs / generatedQuestions
        payload. Once status is COMPLETED / COMPLETED_WITH_ERRORS / FAILED,
        the frontend should switch to GET /generation-requests/{id}/ for
        the full result.
        """
        generation_request = self.get_object()
        serializer = self.get_serializer(generation_request)
        return Response(serializer.data)


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
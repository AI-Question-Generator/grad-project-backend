from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GenerationRequestViewSet, GeneratedQuestionViewSet

router = DefaultRouter()
router.register(r'generation-requests', GenerationRequestViewSet, basename='generation-request')
router.register(r'generated-questions', GeneratedQuestionViewSet, basename='generated-question')

urlpatterns = [
    path('', include(router.urls)),
]

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProjectViewSet, SourceFileViewSet, LessonViewSet, LessonSourceViewSet

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'source-files', SourceFileViewSet, basename='source-file')
router.register(r'lessons', LessonViewSet, basename='lesson')
router.register(r'lesson-sources', LessonSourceViewSet, basename='lesson-source')

urlpatterns = [
    path('', include(router.urls)),
]

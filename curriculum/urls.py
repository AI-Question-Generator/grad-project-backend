from django.urls import path
from .views import FileUploadView, LessonCreateView

urlpatterns = [
    path('upload/', FileUploadView.as_view(), name='file_upload'),
    path('lessons/', LessonCreateView.as_view(), name='lesson_create'),
]

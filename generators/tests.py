import uuid
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from curriculum.models import Project, Lesson
from generators.models import GenerationRequest, GeneratedQuestion
from generators.tasks import process_generation_request
from unittest.mock import patch

User = get_user_model()

class GenerationAPITestCase(APITestCase):
    def setUp(self):
        # Create user & authenticate
        self.user = User.objects.create_user(username='test_user', password='password123', email='test@example.com')
        self.client.force_authenticate(user=self.user)
        
        # Create Project & Lesson
        self.project = Project.objects.create(name='Test Project', owner=self.user)
        self.lesson = Lesson.objects.create(project=self.project, title='Test Lesson')

    @patch('generators.views.process_generation_request.delay')
    def test_create_generation_request(self, mock_delay):
        """
        Ensure we can successfully request a generation task and 
        that it fires off the celery worker.
        """
        url = reverse('generation-request-list')  # from DefaultRouter
        data = {'lesson': str(self.lesson.id)}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(GenerationRequest.objects.count(), 1)
        self.assertEqual(GenerationRequest.objects.get().status, 'PENDING')
        
        # Ensure the Celery task was delayed
        mock_delay.assert_called_once()
        self.assertEqual(str(mock_delay.call_args[0][0]), response.data['id'])

    def test_process_generation_request_task(self):
        """
        Test the celery task synchronous logic explicitly.
        """
        gen_req = GenerationRequest.objects.create(lesson=self.lesson)
        
        with patch('generators.tasks.time.sleep', return_value=None):
            # Run the task synchronously
            process_generation_request(gen_req.id)
            
        gen_req.refresh_from_db()
        self.assertEqual(gen_req.status, 'COMPLETED')

    def test_fetch_completed_questions_access(self):
        """
        Test fetching finalized questions. Ensure RBAC holds true.
        """
        GeneratedQuestion.objects.create(
            lesson=self.lesson, 
            question_type="mcq", 
            content="What is 2+2?", 
            correct_answer="4", 
            chunk_hash="ab12cd34"
        )
        url = reverse('generated-question-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['content'], "What is 2+2?")

        # Test RBAC with a different user
        other_user = User.objects.create_user(username='hacker', password='password123')
        self.client.force_authenticate(user=other_user)
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return empty list because 'hacker' does not own the project linking this lesson
        self.assertEqual(len(response.data), 0)

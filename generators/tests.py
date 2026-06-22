from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from curriculum.models import Project, Lesson, SourceFile, LessonSource
from generators.models import GenerationRequest, GeneratedQuestion, QuestionType
from generators.tasks import process_generation_request

User = get_user_model()


class GenerationAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='test_user',
            password='password123',
            email='test@example.com',
            role='member',
        )
        self.client.force_authenticate(user=self.user)

        self.project = Project.objects.create(name='Test Project', owner=self.user)
        self.lesson = Lesson.objects.create(project=self.project, title='Test Lesson')
        self.lesson2 = Lesson.objects.create(project=self.project, title='Second Lesson')

        self.mcq_type = QuestionType.objects.get(code='mcq')
        self.tf_type = QuestionType.objects.get(code='tf')

    @patch('generators.views.process_generation_request.delay')
    def test_create_generation_request(self, mock_delay):
        url = reverse('generation-request-list')
        data = {
            'project': str(self.project.id),
            'lesson_ids': [str(self.lesson.id), str(self.lesson2.id)],
            'question_type_ids': [str(self.mcq_type.id), str(self.tf_type.id)],
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(GenerationRequest.objects.count(), 1)
        generation_request = GenerationRequest.objects.get()
        self.assertEqual(generation_request.status, 'PENDING')
        self.assertEqual(generation_request.lessons.count(), 2)
        self.assertEqual(generation_request.question_types.count(), 2)
        mock_delay.assert_called_once()

    def test_list_generation_requests_scoped_to_user(self):
        GenerationRequest.objects.create(user=self.user, project=self.project)
        other_user = User.objects.create_user(username='other', password='password123')
        other_project = Project.objects.create(name='Other', owner=other_user)
        GenerationRequest.objects.create(user=other_user, project=other_project)

        response = self.client.get(reverse('generation-request-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        requests = data if isinstance(data, list) else data.get('results', data)
        self.assertEqual(len(requests), 1)

    def test_delete_generation_request_blocks_processing_status(self):
        generation_request = GenerationRequest.objects.create(
            user=self.user,
            project=self.project,
            status='PROCESSING',
        )
        generation_request.lessons.add(self.lesson)

        response = self.client.delete(reverse('generation-request-detail', args=[generation_request.id]))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(GenerationRequest.objects.filter(id=generation_request.id).exists())

    def test_delete_generation_request_success(self):
        generation_request = GenerationRequest.objects.create(
            user=self.user,
            project=self.project,
            status='COMPLETED',
        )
        generation_request.lessons.add(self.lesson)

        response = self.client.delete(reverse('generation-request-detail', args=[generation_request.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(GenerationRequest.objects.filter(id=generation_request.id).exists())

    def test_process_generation_request_task(self):
        generation_request = GenerationRequest.objects.create(user=self.user, project=self.project)
        generation_request.lessons.add(self.lesson)
        generation_request.question_types.add(self.mcq_type)

        with patch('generators.tasks.time.sleep', return_value=None):
            process_generation_request(str(generation_request.id))

        generation_request.refresh_from_db()
        self.assertEqual(generation_request.status, 'COMPLETED')
        self.assertEqual(generation_request.generated_questions.count(), 1)

    def test_fetch_completed_questions_access(self):
        generation_request = GenerationRequest.objects.create(user=self.user, project=self.project)
        GeneratedQuestion.objects.create(
            lesson=self.lesson,
            generation_request=generation_request,
            question_type=self.mcq_type,
            content='What is 2+2?',
            correct_answer='4',
            chunk_hash='ab12cd34',
        )

        url = reverse('generated-question-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        questions = data if isinstance(data, list) else data.get('results', data)
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]['content'], 'What is 2+2?')

        other_user = User.objects.create_user(username='hacker', password='password123')
        self.client.force_authenticate(user=other_user)

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        questions = data if isinstance(data, list) else data.get('results', data)
        self.assertEqual(len(questions), 0)

    def test_filter_generated_questions_by_generation_request(self):
        generation_request = GenerationRequest.objects.create(user=self.user, project=self.project)
        other_request = GenerationRequest.objects.create(user=self.user, project=self.project)

        GeneratedQuestion.objects.create(
            lesson=self.lesson,
            generation_request=generation_request,
            question_type=self.mcq_type,
            content='Question A',
            correct_answer='A',
            chunk_hash='hash-a',
        )
        GeneratedQuestion.objects.create(
            lesson=self.lesson,
            generation_request=other_request,
            question_type=self.tf_type,
            content='Question B',
            correct_answer='True',
            chunk_hash='hash-b',
        )

        url = reverse('generated-question-list')
        response = self.client.get(url, {'generation_request': str(generation_request.id)})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        questions = data if isinstance(data, list) else data.get('results', data)
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]['content'], 'Question A')

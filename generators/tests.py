from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from curriculum.models import Project, Lesson, SourceFile, LessonSource
from generators.models import GenerationRequest, GenerationRequestQuestionConfig, GeneratedQuestion, QuestionType
from generators.tasks import process_generation_request, build_ai_tasks

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
            'lessons': [
                {
                    'lesson_id': str(self.lesson.id),
                    'question_types': [
                        {'question_type_id': str(self.mcq_type.id), 'num_questions': 2},
                        {'question_type_id': str(self.tf_type.id), 'num_questions': 1},
                    ],
                },
                {
                    'lesson_id': str(self.lesson2.id),
                    'question_types': [
                        {'question_type_id': str(self.mcq_type.id), 'num_questions': 1},
                    ],
                },
            ],
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(GenerationRequest.objects.count(), 1)
        generation_request = GenerationRequest.objects.get()
        self.assertEqual(generation_request.status, 'PENDING')
        self.assertEqual(generation_request.lessons.count(), 2)
        self.assertEqual(generation_request.question_configs.count(), 3)
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

    @patch('generators.tasks.AIServiceClient')
    def test_process_generation_request_task(self, MockClient):
        from generators.services import AIServiceClient as RealClient

        real = RealClient(allow_mock=True)
        MockClient.return_value.safe_generate_questions.side_effect = (
            lambda tasks, timeout=None: real.mock_generate_questions(tasks)
        )

        generation_request = GenerationRequest.objects.create(user=self.user, project=self.project)
        generation_request.lessons.add(self.lesson)
        GenerationRequestQuestionConfig.objects.create(
            generation_request=generation_request,
            lesson=self.lesson,
            question_type=self.mcq_type,
            num_questions=1,
        )

        process_generation_request(str(generation_request.id))

        generation_request.refresh_from_db()
        self.assertEqual(generation_request.status, 'COMPLETED')
        self.assertEqual(generation_request.generated_questions.count(), 1)

    @patch('generators.tasks.AIServiceClient')
    def test_empty_ai_response_marks_failed_not_completed(self, MockClient):
        """
        Regression: an AI response with no usable questions must NOT be
        reported as COMPLETED with zero questions.
        """
        MockClient.return_value.safe_generate_questions.side_effect = (
            lambda tasks, timeout=None: {'results': []}
        )

        generation_request = GenerationRequest.objects.create(user=self.user, project=self.project)
        generation_request.lessons.add(self.lesson)
        GenerationRequestQuestionConfig.objects.create(
            generation_request=generation_request,
            lesson=self.lesson,
            question_type=self.tf_type,
            num_questions=20,
        )

        process_generation_request(str(generation_request.id))

        generation_request.refresh_from_db()
        self.assertEqual(generation_request.status, 'FAILED')
        self.assertEqual(generation_request.generated_questions.count(), 0)
        self.assertTrue(generation_request.error_log)

    @patch('generators.tasks.AIServiceClient')
    def test_partial_generation_marks_completed_with_errors(self, MockClient):
        """A lesson that yields questions and one that yields none -> COMPLETED_WITH_ERRORS."""
        from generators.services import AIServiceClient as RealClient

        real = RealClient(allow_mock=True)

        def partial_generate(tasks, timeout=None):
            # Only lesson2 (project_id) gets real questions; lesson yields none.
            served = [t for t in tasks if t['project_id'] == str(self.lesson2.id)]
            if served:
                return real.mock_generate_questions(served)
            return {'results': []}

        MockClient.return_value.safe_generate_questions.side_effect = partial_generate

        generation_request = GenerationRequest.objects.create(user=self.user, project=self.project)
        generation_request.lessons.add(self.lesson, self.lesson2)
        GenerationRequestQuestionConfig.objects.create(
            generation_request=generation_request,
            lesson=self.lesson,
            question_type=self.mcq_type,
            num_questions=5,
        )
        GenerationRequestQuestionConfig.objects.create(
            generation_request=generation_request,
            lesson=self.lesson2,
            question_type=self.tf_type,
            num_questions=5,
        )

        process_generation_request(str(generation_request.id))

        generation_request.refresh_from_db()
        self.assertEqual(generation_request.status, 'COMPLETED_WITH_ERRORS')
        self.assertEqual(generation_request.generated_questions.count(), 5)
        self.assertTrue(generation_request.error_log)

    def test_build_ai_tasks_batches_large_lesson(self):
        generation_request = GenerationRequest.objects.create(user=self.user, project=self.project)
        generation_request.lessons.add(self.lesson)
        GenerationRequestQuestionConfig.objects.create(
            generation_request=generation_request,
            lesson=self.lesson,
            question_type=self.mcq_type,
            num_questions=25,
        )

        payload = build_ai_tasks(generation_request, batch_size=10)
        tasks = payload['tasks']

        # 25 questions / batch of 10 -> three bounded requests.
        self.assertEqual(len(tasks), 3)
        counts = [sum(r['num_questions'] for r in task['requests']) for task in tasks]
        self.assertEqual(sorted(counts, reverse=True), [10, 10, 5])
        self.assertTrue(all(c <= 10 for c in counts))
        self.assertEqual(sum(counts), 25)
        self.assertTrue(all(task['project_id'] == str(self.lesson.id) for task in tasks))

    def test_build_ai_tasks_packs_multiple_types_into_batch(self):
        generation_request = GenerationRequest.objects.create(user=self.user, project=self.project)
        generation_request.lessons.add(self.lesson)
        GenerationRequestQuestionConfig.objects.create(
            generation_request=generation_request,
            lesson=self.lesson,
            question_type=self.mcq_type,
            num_questions=3,
        )
        GenerationRequestQuestionConfig.objects.create(
            generation_request=generation_request,
            lesson=self.lesson,
            question_type=self.tf_type,
            num_questions=4,
        )

        payload = build_ai_tasks(generation_request, batch_size=10)

        # 3 + 4 = 7 <= batch size, so a single request covers both types.
        self.assertEqual(len(payload['tasks']), 1)
        self.assertEqual(len(payload['tasks'][0]['requests']), 2)

    @patch('generators.tasks.AIServiceClient')
    def test_process_generation_request_with_many_questions(self, MockClient):
        """
        End-to-end: a large job (80 questions across two lessons) must be
        split into bounded batches, every batch stays within the batch
        size, and all questions are persisted.
        """
        from generators.services import AIServiceClient as RealClient

        real = RealClient(allow_mock=True)
        batch_totals = []

        def fake_safe_generate(tasks, timeout=None):
            # Each call handles exactly one lesson's batch; record how many
            # questions it was asked to generate so we can assert bounds.
            total = sum(r['num_questions'] for t in tasks for r in t['requests'])
            batch_totals.append(total)
            return real.mock_generate_questions(tasks)

        MockClient.return_value.safe_generate_questions.side_effect = fake_safe_generate

        generation_request = GenerationRequest.objects.create(user=self.user, project=self.project)
        generation_request.lessons.add(self.lesson, self.lesson2)
        GenerationRequestQuestionConfig.objects.create(
            generation_request=generation_request,
            lesson=self.lesson,
            question_type=self.mcq_type,
            num_questions=50,
        )
        GenerationRequestQuestionConfig.objects.create(
            generation_request=generation_request,
            lesson=self.lesson2,
            question_type=self.tf_type,
            num_questions=30,
        )

        process_generation_request(str(generation_request.id))

        generation_request.refresh_from_db()
        self.assertEqual(generation_request.status, 'COMPLETED')

        # Default batch size is 10: 50 -> 5 calls, 30 -> 3 calls = 8 calls.
        self.assertEqual(len(batch_totals), 8)
        self.assertTrue(all(total <= 10 for total in batch_totals))
        self.assertEqual(sum(batch_totals), 80)

        # Every requested question is generated and stored.
        self.assertEqual(generation_request.generated_questions.count(), 80)
        self.assertEqual(
            generation_request.generated_questions.filter(question_type=self.mcq_type).count(), 50
        )
        self.assertEqual(
            generation_request.generated_questions.filter(question_type=self.tf_type).count(), 30
        )

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

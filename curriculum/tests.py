import io
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from curriculum.models import Project, Lesson, LessonSource, SourceFile

User = get_user_model()


class CurriculumAPITestMixin:
    """Shared setup for curriculum API tests."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='member1', password='testpass123', role='member'
        )
        self.client.force_authenticate(user=self.user)

        self.project1 = Project.objects.create(
            name='Physics 101',
            description='Introduction to Mechanics',
            is_default=True,
            owner=self.user,
        )
        self.project2 = Project.objects.create(
            name='Chemistry 201',
            description=None,
            is_default=False,
            owner=self.user,
        )

        self.source1 = SourceFile.objects.create(
            owner=self.user,
            file_hash='hash1',
            file_url='https://example.com/file1.pdf',
            file_name='file1.pdf',
            file_type='application/pdf',
        )
        self.source2 = SourceFile.objects.create(
            owner=self.user,
            file_hash='hash2',
            file_url='https://example.com/file2.pdf',
            file_name='file2.pdf',
            file_type='application/pdf',
        )

        self.lesson1 = Lesson.objects.create(
            project=self.project1,
            title='Newtonian Physics',
            description="Newton's laws of motion",
        )
        self.lesson2 = Lesson.objects.create(
            project=self.project1,
            title='Thermodynamics',
            description='Heat and energy transfer',
        )

        LessonSource.objects.create(
            lesson=self.lesson1,
            source_file=self.source1,
            start_page=1,
            end_page=10,
            order=1,
        )
        LessonSource.objects.create(
            lesson=self.lesson1,
            source_file=self.source2,
            start_page=1,
            end_page=5,
            order=2,
        )
        LessonSource.objects.create(
            lesson=self.lesson2,
            source_file=self.source1,
            start_page=11,
            end_page=20,
            order=1,
        )


class ProjectListResponseShapeTest(CurriculumAPITestMixin, TestCase):
    def test_project_list_response_shape(self):
        response = self.client.get('/api/curriculum/projects/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        projects = data if isinstance(data, list) else data.get('results', data)
        self.assertGreaterEqual(len(projects), 2)

        expected_fields = {'id', 'name', 'description', 'isDefault', 'lessonCount', 'createdAt', 'lessons'}
        for project in projects:
            self.assertEqual(set(project.keys()), expected_fields)


class ProjectListLessonCountTest(CurriculumAPITestMixin, TestCase):
    def test_project_list_lesson_count_accuracy(self):
        response = self.client.get('/api/curriculum/projects/')
        data = response.json()
        projects = data if isinstance(data, list) else data.get('results', data)

        for project in projects:
            self.assertEqual(project['lessonCount'], len(project['lessons']))

        p1 = next(p for p in projects if p['id'] == str(self.project1.id))
        p2 = next(p for p in projects if p['id'] == str(self.project2.id))
        self.assertEqual(p1['lessonCount'], 2)
        self.assertEqual(p2['lessonCount'], 0)


class ProjectListNestedLessonsTest(CurriculumAPITestMixin, TestCase):
    def test_project_list_includes_nested_lessons(self):
        response = self.client.get('/api/curriculum/projects/')
        data = response.json()
        projects = data if isinstance(data, list) else data.get('results', data)

        p1 = next(p for p in projects if p['id'] == str(self.project1.id))
        self.assertEqual(len(p1['lessons']), 2)

        expected_lesson_fields = {
            'id',
            'name',
            'description',
            'unitNumber',
            'section',
            'order',
            'sourceCount',
            'createdAt',
            'sources',
        }
        for lesson in p1['lessons']:
            self.assertEqual(set(lesson.keys()), expected_lesson_fields)


class LessonNameMapsTitleTest(CurriculumAPITestMixin, TestCase):
    def test_lesson_name_maps_title(self):
        response = self.client.get('/api/curriculum/projects/')
        data = response.json()
        projects = data if isinstance(data, list) else data.get('results', data)

        p1 = next(p for p in projects if p['id'] == str(self.project1.id))
        lesson_names = {lesson['name'] for lesson in p1['lessons']}
        self.assertIn('Newtonian Physics', lesson_names)
        self.assertIn('Thermodynamics', lesson_names)


class ProjectDetailSameShapeTest(CurriculumAPITestMixin, TestCase):
    def test_project_detail_same_shape_as_list(self):
        list_response = self.client.get('/api/curriculum/projects/')
        list_data = list_response.json()
        list_projects = list_data if isinstance(list_data, list) else list_data.get('results', list_data)

        detail_response = self.client.get(f'/api/curriculum/projects/{self.project1.id}/')
        detail_data = detail_response.json()

        self.assertEqual(set(list_projects[0].keys()), set(detail_data.keys()))


class LegacyLessonEndpointUnchangedTest(CurriculumAPITestMixin, TestCase):
    def test_legacy_lesson_endpoint_unchanged(self):
        response = self.client.get('/api/curriculum/lessons/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        lessons = data if isinstance(data, list) else data.get('results', data)
        self.assertGreaterEqual(len(lessons), 2)

        for lesson in lessons:
            self.assertIn('title', lesson)
            self.assertIn('project', lesson)
            self.assertNotIn('name', lesson)


class NestedProjectCreateTest(CurriculumAPITestMixin, TestCase):
    @patch('curriculum.views.setup_project_ai.delay')
    def test_create_project_with_nested_lessons_and_sources(self, mock_delay):
        payload = {
            'name': 'Biology 301',
            'description': 'Cell biology fundamentals',
            'lessons': [
                {
                    'title': 'Cells',
                    'description': 'Intro to cells',
                    'unit_number': 1,
                    'section': 'grammar',
                    'order': 2,
                    'sources': [
                        {
                            'source_file': str(self.source1.id),
                            'start_page': 1,
                            'end_page': 8,
                            'order': 0,
                        }
                    ],
                }
            ],
        }
        response = self.client.post('/api/curriculum/projects/', payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['setup']['setupStatus'], 'PENDING')
        project = Project.objects.get(name='Biology 301')
        self.assertEqual(project.lessons.count(), 1)
        lesson = project.lessons.first()
        self.assertEqual(lesson.unit_number, 1)
        self.assertEqual(lesson.section, 'grammar')
        self.assertEqual(lesson.order, 2)
        self.assertEqual(lesson.sources.count(), 1)
        self.assertEqual(lesson.sources.first().start_page, 1)
        mock_delay.assert_called_once()


class SyncAiLessonsTest(CurriculumAPITestMixin, TestCase):
    def test_sync_ai_imports_lessons_with_grouping_fields(self):
        admin = User.objects.create_user(username='admin', password='testpass123', role='admin')
        self.client.force_authenticate(user=admin)

        project_id = '8c03012d-e439-45f3-afb5-112f5ff89dd6'
        first_lesson_id = 'fbec5ffc-61e7-40ba-8c4c-c12ba4514fa7'
        second_lesson_id = '15328480-02a8-47c6-8348-d64aceb13a03'
        payload = {
            'projects': [
                {
                    'id': project_id,
                    'name': 'English Curriculum',
                    'lessons': [
                        {
                            'id': first_lesson_id,
                            'title': 'Vocabulary',
                            'unit_number': 1,
                            'section': '1',
                            'order': 0,
                        },
                        {
                            'id': second_lesson_id,
                            'title': 'Past Simple',
                            'unit_number': 1,
                            'section': 'grammar',
                            'order': 0,
                        },
                    ],
                },
            ],
        }

        response = self.client.post('/api/curriculum/projects/sync-ai/', payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['imported'], [project_id])

        project = Project.objects.get(id=project_id)
        self.assertTrue(project.is_default)
        self.assertEqual(project.lessons.count(), 2)

        first_lesson = Lesson.objects.get(id=first_lesson_id)
        self.assertEqual(first_lesson.project, project)
        self.assertEqual(first_lesson.title, 'Vocabulary')
        self.assertEqual(first_lesson.unit_number, 1)
        self.assertEqual(first_lesson.section, '1')
        self.assertEqual(first_lesson.order, 0)

        second_lesson = Lesson.objects.get(id=second_lesson_id)
        self.assertEqual(second_lesson.title, 'Past Simple')
        self.assertEqual(second_lesson.unit_number, 1)
        self.assertEqual(second_lesson.section, 'grammar')
        self.assertEqual(second_lesson.order, 0)


class NestedProjectUpdateReplaceLessonsTest(CurriculumAPITestMixin, TestCase):
    def test_update_project_replaces_lessons_when_lessons_key_present(self):
        payload = {
            'name': self.project2.name,
            'lessons': [
                {
                    'title': 'Only Lesson',
                    'sources': [
                        {
                            'source_file': str(self.source1.id),
                            'start_page': 2,
                            'end_page': 4,
                            'order': 0,
                        }
                    ],
                }
            ],
        }
        response = self.client.put(
            f'/api/curriculum/projects/{self.project2.id}/',
            payload,
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.project2.refresh_from_db()
        self.assertEqual(self.project2.lessons.count(), 1)
        self.assertEqual(self.project2.lessons.first().title, 'Only Lesson')


class DefaultProjectReadOnlyTest(CurriculumAPITestMixin, TestCase):
    def test_default_project_cannot_be_modified(self):
        payload = {'name': 'Updated Default Project'}

        update_response = self.client.put(
            f'/api/curriculum/projects/{self.project1.id}/',
            payload,
            format='json',
        )
        self.assertEqual(update_response.status_code, status.HTTP_400_BAD_REQUEST)

        delete_response = self.client.delete(f'/api/curriculum/projects/{self.project1.id}/')
        self.assertEqual(delete_response.status_code, status.HTTP_403_FORBIDDEN)


class DefaultProjectVisibilityTest(CurriculumAPITestMixin, TestCase):
    def test_default_project_is_visible_to_other_users(self):
        other_user = User.objects.create_user(username='viewer', password='testpass123', role='member')
        self.client.force_authenticate(user=other_user)

        response = self.client.get('/api/curriculum/projects/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        projects = data if isinstance(data, list) else data.get('results', data)
        project_ids = {project['id'] for project in projects}
        self.assertIn(str(self.project1.id), project_ids)


class ProjectSetupStatusTest(CurriculumAPITestMixin, TestCase):
    def test_setup_status_endpoint_returns_feedback(self):
        self.project2.ai_setup_status = 'COMPLETED'
        self.project2.ai_setup_feedback = 'AI setup completed successfully.'
        self.project2.save(update_fields=['ai_setup_status', 'ai_setup_feedback'])

        response = self.client.get(f'/api/curriculum/projects/{self.project2.id}/setup-status/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['setupStatus'], 'COMPLETED')
        self.assertEqual(response.data['setupFeedback'], 'AI setup completed successfully.')


class ProjectSetupLessonScopedAiCallsTest(CurriculumAPITestMixin, TestCase):
    @patch('curriculum.tasks.AIServiceClient')
    def test_setup_project_ai_uses_lesson_ids(self, mock_ai_client_class):
        mock_client = mock_ai_client_class.return_value
        mock_client.create_project.return_value = None
        mock_client.upload_text.return_value = None
        mock_client.process_project.return_value = None
        mock_client.extract_main_ideas.return_value = None
        mock_client.associate_chunks.return_value = None

        from curriculum.tasks import setup_project_ai

        setup_project_ai(str(self.project1.id))

        lesson_ids = {str(self.lesson1.id), str(self.lesson2.id)}
        create_calls = {call.args[0] for call in mock_client.create_project.call_args_list}
        process_calls = {call.args[0] for call in mock_client.process_project.call_args_list}
        extract_calls = {call.args[0] for call in mock_client.extract_main_ideas.call_args_list}
        associate_calls = {call.args[0] for call in mock_client.associate_chunks.call_args_list}

        self.assertSetEqual(create_calls, lesson_ids)
        self.assertSetEqual(process_calls, lesson_ids)
        self.assertSetEqual(extract_calls, lesson_ids)
        self.assertSetEqual(associate_calls, lesson_ids)

        self.project1.refresh_from_db()
        self.assertEqual(self.project1.ai_setup_status, 'COMPLETED')
        self.assertIn('lesson(s)', self.project1.ai_setup_feedback)


class NestedProjectOwnershipValidationTest(CurriculumAPITestMixin, TestCase):
    def test_create_project_rejects_foreign_source_file(self):
        other_user = User.objects.create_user(username='other', password='testpass123')
        foreign_source = SourceFile.objects.create(
            owner=other_user,
            file_hash='foreign',
            file_url='https://example.com/foreign.pdf',
            file_name='foreign.pdf',
            file_type='application/pdf',
        )

        payload = {
            'name': 'Invalid Project',
            'lessons': [
                {
                    'title': 'Lesson',
                    'sources': [
                        {
                            'source_file': str(foreign_source.id),
                            'start_page': 1,
                            'end_page': 2,
                            'order': 0,
                        }
                    ],
                }
            ],
        }
        response = self.client.post('/api/curriculum/projects/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(MEDIA_ROOT='/tmp/grad-project-test-media')
class SourceFileUploadTest(CurriculumAPITestMixin, TestCase):
    def test_upload_pdf_creates_source_file(self):
        pdf_content = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF'
        upload = SimpleUploadedFile('sample.pdf', pdf_content, content_type='application/pdf')

        response = self.client.post(
            '/api/curriculum/source-files/upload/',
            {'file': upload},
            format='multipart',
        )

        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        self.assertEqual(SourceFile.objects.filter(owner=self.user).count(), 3)

    def test_upload_rejects_non_pdf(self):
        upload = SimpleUploadedFile('notes.txt', b'hello', content_type='text/plain')
        response = self.client.post(
            '/api/curriculum/source-files/upload/',
            {'file': upload},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_upload_allows_same_file_for_different_users(self):
        pdf_content = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF'

        first_upload = SimpleUploadedFile('same.pdf', pdf_content, content_type='application/pdf')
        response1 = self.client.post(
            '/api/curriculum/source-files/upload/',
            {'file': first_upload},
            format='multipart',
        )
        self.assertIn(response1.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])

        other_user = User.objects.create_user(
            username='member2', password='testpass123', role='member'
        )
        self.client.force_authenticate(user=other_user)

        second_upload = SimpleUploadedFile('same.pdf', pdf_content, content_type='application/pdf')
        response2 = self.client.post(
            '/api/curriculum/source-files/upload/',
            {'file': second_upload},
            format='multipart',
        )
        self.assertIn(response2.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])

        self.assertEqual(SourceFile.objects.filter(file_hash=response1.data['fileHash']).count(), 2)

    def test_source_file_allows_only_upload_and_delete(self):
        list_response = self.client.get('/api/curriculum/source-files/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)

        source = SourceFile.objects.create(
            owner=self.user,
            file_hash='delete_hash',
            file_name='to_delete.pdf',
            file_type='application/pdf',
            file_url='https://example.com/to_delete.pdf',
        )

        detail_response = self.client.get(f'/api/curriculum/source-files/{source.id}/')
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)

        self.assertEqual(
            self.client.put(f'/api/curriculum/source-files/{source.id}/').status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertEqual(
            self.client.patch(f'/api/curriculum/source-files/{source.id}/').status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

        delete_response = self.client.delete(f'/api/curriculum/source-files/{source.id}/')
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

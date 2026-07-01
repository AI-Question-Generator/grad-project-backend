import io

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

        expected_lesson_fields = {'id', 'name', 'description', 'sourceCount', 'createdAt', 'sources'}
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
    def test_create_project_with_nested_lessons_and_sources(self):
        payload = {
            'name': 'Biology 301',
            'description': 'Cell biology fundamentals',
            'lessons': [
                {
                    'title': 'Cells',
                    'description': 'Intro to cells',
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
        project = Project.objects.get(name='Biology 301')
        self.assertEqual(project.lessons.count(), 1)
        self.assertEqual(project.lessons.first().sources.count(), 1)
        self.assertEqual(project.lessons.first().sources.first().start_page, 1)


class NestedProjectUpdateReplaceLessonsTest(CurriculumAPITestMixin, TestCase):
    def test_update_project_replaces_lessons_when_lessons_key_present(self):
        payload = {
            'name': self.project1.name,
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
            f'/api/curriculum/projects/{self.project1.id}/',
            payload,
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.project1.refresh_from_db()
        self.assertEqual(self.project1.lessons.count(), 1)
        self.assertEqual(self.project1.lessons.first().title, 'Only Lesson')


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

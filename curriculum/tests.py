from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from curriculum.models import Project, Lesson, LessonSource, SourceFile

User = get_user_model()


class CurriculumAPITestMixin:
    """Shared setup for curriculum API tests."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='teacher1', password='testpass123', role='teacher'
        )
        self.client.force_authenticate(user=self.user)

        # Create two projects
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

        # Create source files
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

        # Create lessons for project1
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

        # Link sources to lessons
        LessonSource.objects.create(
            lesson=self.lesson1, source_file=self.source1, order=1
        )
        LessonSource.objects.create(
            lesson=self.lesson1, source_file=self.source2, order=2
        )
        LessonSource.objects.create(
            lesson=self.lesson2, source_file=self.source1, order=1
        )


class ProjectListResponseShapeTest(CurriculumAPITestMixin, TestCase):
    """Test that the project list response has the correct shape."""

    def test_project_list_response_shape(self):
        response = self.client.get('/api/curriculum/projects/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should have results (or be a list if pagination is off)
        data = response.json()
        projects = data if isinstance(data, list) else data.get('results', data)
        self.assertGreaterEqual(len(projects), 2)

        expected_fields = {'id', 'name', 'description', 'isDefault', 'lessonCount', 'createdAt', 'lessons'}
        for project in projects:
            self.assertEqual(set(project.keys()), expected_fields)


class ProjectListLessonCountTest(CurriculumAPITestMixin, TestCase):
    """Test that lessonCount matches the actual number of nested lessons."""

    def test_project_list_lesson_count_accuracy(self):
        response = self.client.get('/api/curriculum/projects/')
        data = response.json()
        projects = data if isinstance(data, list) else data.get('results', data)

        for project in projects:
            self.assertEqual(project['lessonCount'], len(project['lessons']))

        # Verify specific counts
        p1 = next(p for p in projects if p['id'] == str(self.project1.id))
        p2 = next(p for p in projects if p['id'] == str(self.project2.id))
        self.assertEqual(p1['lessonCount'], 2)
        self.assertEqual(p2['lessonCount'], 0)


class ProjectListNestedLessonsTest(CurriculumAPITestMixin, TestCase):
    """Test that each project's lessons array has the correct shape."""

    def test_project_list_includes_nested_lessons(self):
        response = self.client.get('/api/curriculum/projects/')
        data = response.json()
        projects = data if isinstance(data, list) else data.get('results', data)

        p1 = next(p for p in projects if p['id'] == str(self.project1.id))
        self.assertEqual(len(p1['lessons']), 2)

        expected_lesson_fields = {'id', 'name', 'description', 'sourceCount', 'createdAt'}
        for lesson in p1['lessons']:
            self.assertEqual(set(lesson.keys()), expected_lesson_fields)


class LessonNameMapsTitleTest(CurriculumAPITestMixin, TestCase):
    """Test that lessons[].name maps to the model's title field."""

    def test_lesson_name_maps_title(self):
        response = self.client.get('/api/curriculum/projects/')
        data = response.json()
        projects = data if isinstance(data, list) else data.get('results', data)

        p1 = next(p for p in projects if p['id'] == str(self.project1.id))
        lesson_names = {l['name'] for l in p1['lessons']}
        self.assertIn('Newtonian Physics', lesson_names)
        self.assertIn('Thermodynamics', lesson_names)


class ProjectListQueryCountTest(CurriculumAPITestMixin, TestCase):
    """Test that the list endpoint is query-efficient."""

    def test_project_list_query_count(self):
        # 2 queries: projects+annotation in one, prefetch lessons+source_count in one
        with self.assertNumQueries(2):
            self.client.get('/api/curriculum/projects/')


class ProjectDetailSameShapeTest(CurriculumAPITestMixin, TestCase):
    """Test that detail response has the same shape as list items."""

    def test_project_detail_same_shape_as_list(self):
        list_response = self.client.get('/api/curriculum/projects/')
        list_data = list_response.json()
        list_projects = list_data if isinstance(list_data, list) else list_data.get('results', list_data)

        detail_response = self.client.get(f'/api/curriculum/projects/{self.project1.id}/')
        detail_data = detail_response.json()

        self.assertEqual(set(list_projects[0].keys()), set(detail_data.keys()))


class LegacyLessonEndpointUnchangedTest(CurriculumAPITestMixin, TestCase):
    """Test that the flat /lessons/ endpoint still works as before."""

    def test_legacy_lesson_endpoint_unchanged(self):
        response = self.client.get('/api/curriculum/lessons/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        lessons = data if isinstance(data, list) else data.get('results', data)
        self.assertGreaterEqual(len(lessons), 2)

        # Legacy endpoint uses 'title', not 'name'
        for lesson in lessons:
            self.assertIn('title', lesson)
            self.assertIn('project', lesson)
            self.assertNotIn('name', lesson)


class CreateProjectWriteSerializerTest(CurriculumAPITestMixin, TestCase):
    """Test that POST still uses the original ProjectSerializer."""

    def test_create_project_still_uses_write_serializer(self):
        response = self.client.post('/api/curriculum/projects/', {
            'name': 'Biology 301',
            'description': 'Cell biology fundamentals',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        # Write serializer returns all model fields
        self.assertIn('name', data)
        self.assertIn('owner', data)
        self.assertEqual(data['name'], 'Biology 301')

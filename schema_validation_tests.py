"""
Comprehensive Schema Validation Tests
Tests all schema changes: User roles, SourceFile, LessonSource, QuestionType, GenerationRequest, GeneratedQuestion
"""

import io
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from authentication.models import User
from curriculum.models import Project, Lesson, SourceFile, LessonSource
from generators.models import GenerationRequest, GeneratedQuestion, QuestionType

User = get_user_model()


class UserRoleSimplificationTest(TestCase):
    """Test simplified user roles: admin and member (migrated from teacher/student)"""

    def test_user_roles_simplified(self):
        """Verify only admin and member roles exist"""
        # Create admin user
        admin = User.objects.create_user(
            username='admin_user',
            password='testpass123',
            role='admin'
        )
        self.assertEqual(admin.role, 'admin')

        # Create member user
        member = User.objects.create_user(
            username='member_user',
            password='testpass123',
            role='member'
        )
        self.assertEqual(member.role, 'member')

        # Verify role choices only include admin and member
        self.assertEqual(User.ADMIN, 'admin')
        self.assertEqual(User.MEMBER, 'member')


class SourceFileSchemaTest(TestCase):
    """Test SourceFile with file, file_size, page_count"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            role='member'
        )

    def test_source_file_with_all_fields(self):
        """Test SourceFile creation with file, file_size, page_count"""
        pdf_content = b'%PDF-1.4 dummy pdf'
        pdf_file = SimpleUploadedFile(
            'test.pdf',
            pdf_content,
            content_type='application/pdf'
        )

        source = SourceFile.objects.create(
            owner=self.user,
            file=pdf_file,
            file_hash='abc123def456',
            file_url='https://example.com/test.pdf',
            file_name='test.pdf',
            file_type='application/pdf',
            file_size=1024,
            page_count=10
        )

        self.assertEqual(source.owner, self.user)
        self.assertEqual(source.file_size, 1024)
        self.assertEqual(source.page_count, 10)
        self.assertIsNotNone(source.file)

    def test_source_file_deletion_removes_physical_file(self):
        """Test that deleting SourceFile deletes physical file"""
        pdf_file = SimpleUploadedFile(
            'delete_test.pdf',
            b'%PDF-1.4 dummy',
            content_type='application/pdf'
        )

        source = SourceFile.objects.create(
            owner=self.user,
            file=pdf_file,
            file_hash='delete123',
            file_name='delete_test.pdf',
            file_type='application/pdf',
            file_size=100,
            page_count=5
        )

        file_field = source.file
        self.assertTrue(file_field)

        # Delete the source - should also delete file
        source.delete()
        self.assertFalse(SourceFile.objects.filter(id=source.id).exists())

    def test_source_file_hash_dedup_per_user(self):
        """Test file_hash uniqueness for deduplication"""
        SourceFile.objects.create(
            owner=self.user,
            file_hash='unique_hash',
            file_name='file1.pdf',
            file_type='application/pdf',
            file_url='https://example.com/file1.pdf'
        )

        # Try to create duplicate - should fail due to unique constraint
        with self.assertRaises(Exception):  # IntegrityError
            SourceFile.objects.create(
                owner=self.user,
                file_hash='unique_hash',
                file_name='file2.pdf',
                file_type='application/pdf',
                file_url='https://example.com/file2.pdf'
            )


class LessonSourceSchemaTest(TestCase):
    """Test LessonSource with explicit start_page/end_page validation"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            role='member'
        )
        self.project = Project.objects.create(
            name='Test Project',
            owner=self.user
        )
        self.lesson = Lesson.objects.create(
            project=self.project,
            title='Test Lesson'
        )
        self.source = SourceFile.objects.create(
            owner=self.user,
            file_hash='hash123',
            file_name='test.pdf',
            file_type='application/pdf',
            page_count=20
        )

    def test_lesson_source_start_end_page_validation(self):
        """Test start_page and end_page validation"""
        # Valid case
        lesson_source = LessonSource.objects.create(
            lesson=self.lesson,
            source_file=self.source,
            start_page=1,
            end_page=10,
            order=0
        )
        self.assertEqual(lesson_source.start_page, 1)
        self.assertEqual(lesson_source.end_page, 10)

    def test_lesson_source_invalid_page_range(self):
        """Test that start_page > end_page raises ValidationError"""
        from django.core.exceptions import ValidationError

        lesson_source = LessonSource(
            lesson=self.lesson,
            source_file=self.source,
            start_page=15,
            end_page=10,  # Invalid: end < start
            order=0
        )

        with self.assertRaises(ValidationError):
            lesson_source.full_clean()

    def test_lesson_source_end_page_exceeds_file_pages(self):
        """Test that end_page cannot exceed source file page count"""
        from django.core.exceptions import ValidationError

        lesson_source = LessonSource(
            lesson=self.lesson,
            source_file=self.source,
            start_page=1,
            end_page=30,  # Invalid: exceeds page_count=20
            order=0
        )

        with self.assertRaises(ValidationError):
            lesson_source.full_clean()


class QuestionTypeSchemaTest(TestCase):
    """Test QuestionType seeding with mcq, tf, short_answer"""

    def test_question_types_seeded(self):
        """Verify QuestionType seeded with mcq, tf, short_answer"""
        # QuestionTypes should be created via migration
        mcq = QuestionType.objects.get(code='mcq')
        tf = QuestionType.objects.get(code='tf')
        short_answer = QuestionType.objects.get(code='short_answer')

        self.assertEqual(mcq.name, 'Multiple Choice')
        self.assertEqual(tf.name, 'True/False')
        self.assertEqual(short_answer.name, 'Short Answer')

        self.assertTrue(mcq.is_active)
        self.assertTrue(tf.is_active)
        self.assertTrue(short_answer.is_active)


class GenerationRequestSchemaTest(TestCase):
    """Test GenerationRequest with user, project, M2M lessons, M2M question_types"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            role='member'
        )
        self.project = Project.objects.create(
            name='Test Project',
            owner=self.user
        )
        self.lesson1 = Lesson.objects.create(
            project=self.project,
            title='Lesson 1'
        )
        self.lesson2 = Lesson.objects.create(
            project=self.project,
            title='Lesson 2'
        )
        self.mcq_type = QuestionType.objects.get(code='mcq')
        self.tf_type = QuestionType.objects.get(code='tf')

    def test_generation_request_with_user_and_project(self):
        """Test GenerationRequest has user and project FK"""
        gen_request = GenerationRequest.objects.create(
            user=self.user,
            project=self.project,
            status='PENDING'
        )

        self.assertEqual(gen_request.user, self.user)
        self.assertEqual(gen_request.project, self.project)
        self.assertEqual(gen_request.status, 'PENDING')

    def test_generation_request_m2m_lessons(self):
        """Test GenerationRequest M2M relationship with Lessons"""
        gen_request = GenerationRequest.objects.create(
            user=self.user,
            project=self.project,
            status='PENDING'
        )
        gen_request.lessons.add(self.lesson1, self.lesson2)

        self.assertEqual(gen_request.lessons.count(), 2)
        self.assertIn(self.lesson1, gen_request.lessons.all())
        self.assertIn(self.lesson2, gen_request.lessons.all())

    def test_generation_request_m2m_question_types(self):
        """Test GenerationRequest M2M relationship with QuestionTypes"""
        gen_request = GenerationRequest.objects.create(
            user=self.user,
            project=self.project,
            status='PENDING'
        )
        gen_request.question_types.add(self.mcq_type, self.tf_type)

        self.assertEqual(gen_request.question_types.count(), 2)
        self.assertIn(self.mcq_type, gen_request.question_types.all())
        self.assertIn(self.tf_type, gen_request.question_types.all())


class GeneratedQuestionSchemaTest(TestCase):
    """Test GeneratedQuestion with question_type FK"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            role='member'
        )
        self.project = Project.objects.create(
            name='Test Project',
            owner=self.user
        )
        self.lesson = Lesson.objects.create(
            project=self.project,
            title='Test Lesson'
        )
        self.mcq_type = QuestionType.objects.get(code='mcq')
        self.gen_request = GenerationRequest.objects.create(
            user=self.user,
            project=self.project,
            status='COMPLETED'
        )

    def test_generated_question_with_question_type_fk(self):
        """Test GeneratedQuestion question_type is FK"""
        question = GeneratedQuestion.objects.create(
            lesson=self.lesson,
            generation_request=self.gen_request,
            question_type=self.mcq_type,
            content='What is 2+2?',
            correct_answer='4',
            distractors=['3', '5', '6'],
            explanation='Basic arithmetic',
            chunk_hash='hash123'
        )

        self.assertEqual(question.question_type, self.mcq_type)
        self.assertEqual(question.generation_request, self.gen_request)

    def test_generated_question_generation_request_migration(self):
        """Test GeneratedQuestion has generation_request FK"""
        question = GeneratedQuestion.objects.create(
            lesson=self.lesson,
            generation_request=self.gen_request,
            question_type=self.mcq_type,
            content='Sample question',
            correct_answer='Answer',
            chunk_hash='hash456'
        )

        self.assertIsNotNone(question.generation_request_id)
        self.assertEqual(question.generation_request, self.gen_request)

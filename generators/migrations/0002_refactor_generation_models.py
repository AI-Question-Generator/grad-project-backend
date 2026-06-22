import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def seed_question_types(apps, schema_editor):
    QuestionType = apps.get_model('generators', 'QuestionType')
    defaults = [
        ('mcq', 'Multiple Choice'),
        ('tf', 'True/False'),
        ('short_answer', 'Short Answer'),
    ]
    for code, name in defaults:
        QuestionType.objects.get_or_create(code=code, defaults={'name': name, 'is_active': True})


def migrate_generation_requests(apps, schema_editor):
    GenerationRequest = apps.get_model('generators', 'GenerationRequest')
    Lesson = apps.get_model('curriculum', 'Lesson')
    Project = apps.get_model('curriculum', 'Project')

    for request in GenerationRequest.objects.all():
        lesson_id = request.lesson_id
        if not lesson_id:
            request.delete()
            continue

        lesson = Lesson.objects.get(id=lesson_id)
        project = Project.objects.get(id=lesson.project_id)
        request.project_id = project.id
        request.user_id = project.owner_id
        request.save(update_fields=['project_id', 'user_id'])
        request.lessons.add(lesson)


def migrate_generated_questions(apps, schema_editor):
    GeneratedQuestion = apps.get_model('generators', 'GeneratedQuestion')
    QuestionType = apps.get_model('generators', 'QuestionType')
    type_map = {qt.code: qt for qt in QuestionType.objects.all()}

    for question in GeneratedQuestion.objects.all():
        old_type = question.question_type_old
        question_type = type_map.get(old_type)
        if question_type is None:
            question_type = type_map.get('mcq')
        question.question_type = question_type
        question.save(update_fields=['question_type'])


class Migration(migrations.Migration):

    dependencies = [
        ('curriculum', '0003_sourcefile_and_lessonsource_updates'),
        ('generators', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='QuestionType',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('code', models.CharField(max_length=50, unique=True)),
                ('name', models.CharField(max_length=100)),
                ('is_active', models.BooleanField(default=True)),
            ],
        ),
        migrations.RunPython(seed_question_types, migrations.RunPython.noop),
        migrations.AddField(
            model_name='generationrequest',
            name='project',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='generation_requests',
                to='curriculum.project',
            ),
        ),
        migrations.AddField(
            model_name='generationrequest',
            name='user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='generation_requests',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='generationrequest',
            name='lessons',
            field=models.ManyToManyField(blank=True, related_name='generation_requests', to='curriculum.lesson'),
        ),
        migrations.RunPython(migrate_generation_requests, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='generationrequest',
            name='lesson',
        ),
        migrations.AlterField(
            model_name='generationrequest',
            name='project',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='generation_requests',
                to='curriculum.project',
            ),
        ),
        migrations.AlterField(
            model_name='generationrequest',
            name='user',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='generation_requests',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='generationrequest',
            name='question_types',
            field=models.ManyToManyField(blank=True, related_name='generation_requests', to='generators.questiontype'),
        ),
        migrations.AddField(
            model_name='generatedquestion',
            name='generation_request',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='generated_questions',
                to='generators.generationrequest',
            ),
        ),
        migrations.RenameField(
            model_name='generatedquestion',
            old_name='question_type',
            new_name='question_type_old',
        ),
        migrations.AddField(
            model_name='generatedquestion',
            name='question_type',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='generated_questions',
                to='generators.questiontype',
            ),
        ),
        migrations.RunPython(migrate_generated_questions, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='generatedquestion',
            name='question_type_old',
        ),
        migrations.AlterField(
            model_name='generatedquestion',
            name='question_type',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='generated_questions',
                to='generators.questiontype',
            ),
        ),
    ]

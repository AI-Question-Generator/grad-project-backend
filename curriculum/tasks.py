import logging

from celery import shared_task
from django.utils import timezone

from curriculum.models import Project
from curriculum.utils import extract_source_file_text
from generators.services import AIServiceClient

logger = logging.getLogger(__name__)


def _setup_lesson_scope(client, lesson):
    lesson_scope_id = str(lesson.id)
    uploaded_sources = 0

    logger.info('create_project start for lesson %s', lesson_scope_id)
    # Arabic lessons have no domain; English lessons pass their selected domain.
    client.create_project(lesson_scope_id, language=lesson.language, domain=lesson.domain or '')
    logger.info('create_project done for lesson %s', lesson_scope_id)

    for lesson_source in lesson.sources.select_related('source_file').all():
        source_file = lesson_source.source_file
        text = extract_source_file_text(source_file, lesson_source.start_page, lesson_source.end_page)
        if not text.strip():
            continue
        filename = f'{lesson.title}-{source_file.file_name or source_file.id}.txt'
        logger.info('upload_text start for %s', filename)
        client.upload_text(lesson_scope_id, filename, text)
        logger.info('upload_text done for %s', filename)
        uploaded_sources += 1

    logger.info('process_project start for lesson %s', lesson_scope_id)
    client.process_project(lesson_scope_id, do_reset=True)
    logger.info('index_push start for lesson %s', lesson_scope_id)
    client.index_push(lesson_scope_id, do_reset=True)
    logger.info('extract_main_ideas start for lesson %s', lesson_scope_id)
    client.extract_main_ideas(lesson_scope_id, do_reset=True)
    logger.info('associate_chunks start for lesson %s', lesson_scope_id)
    client.associate_chunks(lesson_scope_id, do_reset=True)

    return uploaded_sources


@shared_task(bind=True)
def setup_project_ai(self, project_id):
    project = Project.objects.prefetch_related(
        'lessons__sources__source_file',
    ).get(id=project_id)

    project.ai_setup_status = Project.SETUP_PROCESSING
    project.ai_setup_started_at = timezone.now()
    project.ai_setup_feedback = 'Setting up AI project...'
    project.save(update_fields=['ai_setup_status', 'ai_setup_started_at', 'ai_setup_feedback'])

    client = AIServiceClient(allow_mock=False)
    errors = []
    uploaded_sources = 0
    successful_lessons = 0

    try:
        for lesson in project.lessons.all():
            try:
                uploaded_sources += _setup_lesson_scope(client, lesson)
                successful_lessons += 1
            except Exception as exc:
                logger.exception('AI project setup failed for lesson %s in project %s', lesson.id, project_id)
                errors.append(f'lesson {lesson.id}: {exc}')

    except Exception as exc:
        logger.exception('AI project setup failed for project %s', project_id)
        errors.append(str(exc))

    if errors:
        project.ai_setup_status = (
            Project.SETUP_COMPLETED_WITH_ERRORS if successful_lessons else Project.SETUP_FAILED
        )
        project.ai_setup_feedback = (
            f'AI setup completed for {successful_lessons} lesson(s) with errors. '
            f'Uploaded {uploaded_sources} source slice(s). Errors: ' + '; '.join(errors)
        )
    else:
        project.ai_setup_status = Project.SETUP_COMPLETED
        if uploaded_sources:
            project.ai_setup_feedback = (
                f'AI setup completed successfully for {successful_lessons} lesson(s). '
                f'Uploaded {uploaded_sources} source slice(s).'
            )
        else:
            project.ai_setup_feedback = (
                f'AI setup completed successfully for {successful_lessons} lesson(s), '
                'but no source text was available to upload.'
            )

    project.ai_setup_completed_at = timezone.now()
    project.save(update_fields=['ai_setup_status', 'ai_setup_feedback', 'ai_setup_completed_at'])

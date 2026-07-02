import uuid
import logging

import requests
from celery import shared_task
from django.utils import timezone

from .models import GenerationRequest, GeneratedQuestion, QuestionType
from .services import AIServiceClient

logger = logging.getLogger(__name__)

AI_SUCCESS_SIGNAL = 'Question generation completed successfully'


def build_ai_tasks(req):
    tasks = []
    configs_by_lesson = {}
    for config in req.question_configs.select_related('lesson', 'question_type').all():
        configs_by_lesson.setdefault(config.lesson_id, []).append(config)

    for lesson in req.lessons.all():
        lesson_configs = configs_by_lesson.get(lesson.id, [])
        if not lesson_configs:
            continue
        tasks.append({
            "project_id": str(lesson.id),
            "requests": [
                {
                    "num_questions": config.num_questions,
                    "question_type": config.question_type.code,
                }
                for config in lesson_configs
            ],
        })

    return {"tasks": tasks}


def process_ai_response(req, ai_response):
    """
    Parse the AI service response and create GeneratedQuestion rows.

    The response can contain multiple entries for the same question_type
    (e.g. one per content chunk processed) - some may have succeeded and
    some may have failed, so we iterate all of them rather than assuming
    one entry per type.

    Returns True if at least one (lesson, question_type) entry failed or
    produced zero questions, so the caller can mark the request as
    'COMPLETED_WITH_ERRORS' instead of 'COMPLETED'.
    """
    lessons_by_id = {str(lesson.id): lesson for lesson in req.lessons.all()}
    types_by_code = {qtype.code: qtype for qtype in QuestionType.objects.filter(is_active=True)}

    had_failures = False

    results = ai_response.get('results')
    if results is None and 'content' in ai_response:
        results = []
        for lesson_result in ai_response.get('content', []):
            results.append(
                {
                    'project_id': lesson_result.get('lesson_id'),
                    'results': [
                        {
                            'question_type': question.get('type'),
                            'questions': {
                                'signal': AI_SUCCESS_SIGNAL,
                                'questions_generated': [question],
                            },
                        }
                        for question in lesson_result.get('questions', [])
                    ],
                }
            )

    for project_result in results or []:
        ai_project_id = project_result.get('project_id')
        lesson = lessons_by_id.get(str(ai_project_id))
        if lesson is None:
            logger.warning("AI response referenced unknown lesson/project_id=%s", ai_project_id)
            had_failures = True
            continue

        for type_result in project_result.get('results', []):
            code = type_result.get('question_type')
            qtype = types_by_code.get(code)
            if qtype is None:
                logger.warning("AI response referenced unknown question_type=%s", code)
                had_failures = True
                continue

            payload = type_result.get('questions', {})
            signal = payload.get('signal')
            questions_generated = payload.get('questions_generated', [])

            if signal != AI_SUCCESS_SIGNAL or not questions_generated:
                had_failures = True
                continue

            for q in questions_generated:
                GeneratedQuestion.objects.create(
                    lesson=lesson,
                    generation_request=req,
                    question_type=qtype,
                    content=q.get('question_statement', ''),
                    correct_answer=q.get('correct_answer', ''),
                    distractors=q.get('plausible_distractors', []),
                    explanation=q.get('explanation', ''),
                    chunk_hash=q.get('chunk_hash') or str(uuid.uuid4()),
                )

    return had_failures


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def process_generation_request(self, request_id):
    req = None
    try:
        req = GenerationRequest.objects.select_related('project').prefetch_related(
            'lessons',
            'question_configs__lesson',
            'question_configs__question_type',
        ).get(id=request_id)

        req.status = 'PROCESSING'
        req.save(update_fields=['status'])

        payload = build_ai_tasks(req)

        if not payload['tasks']:
            req.status = 'FAILED'
            req.error_log = 'No question configurations found for this request.'
            req.completed_at = timezone.now()
            req.save(update_fields=['status', 'error_log', 'completed_at'])
            return

        client = AIServiceClient()
        ai_response = client.safe_generate_questions(payload['tasks'])
        had_failures = process_ai_response(req, ai_response)

        req.status = 'COMPLETED_WITH_ERRORS' if had_failures else 'COMPLETED'
        req.completed_at = timezone.now()
        req.save(update_fields=['status', 'completed_at'])

    except GenerationRequest.DoesNotExist:
        logger.error("GenerationRequest %s not found", request_id)

    except requests.RequestException as exc:
        logger.exception("AI service call failed for request %s", request_id)
        if req:
            req.status = 'FAILED'
            req.error_log = f"AI service error: {exc}"
            req.completed_at = timezone.now()
            req.save(update_fields=['status', 'error_log', 'completed_at'])
        raise self.retry(exc=exc)

    except Exception as exc:
        logger.exception("Unexpected error processing request %s", request_id)
        if req is None:
            req = GenerationRequest.objects.filter(id=request_id).first()
        if req:
            req.status = 'FAILED'
            req.error_log = str(exc)
            req.completed_at = timezone.now()
            req.save(update_fields=['status', 'error_log', 'completed_at'])
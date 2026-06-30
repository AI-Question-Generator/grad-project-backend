import uuid
import logging

import requests
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import GenerationRequest, GeneratedQuestion, QuestionType

logger = logging.getLogger(__name__)

AI_SUCCESS_SIGNAL = 'Question generation completed successfully'


def build_ai_payload(req):
    """
    Build the AI service request payload.

    The AI service's "project_id" is actually our lesson_id - it doesn't
    know about our Project model, it just needs a unique key per lesson
    so it can tell us which generated questions belong to which lesson.
    """
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


def call_ai_service(payload):
    response = requests.post(
        settings.AI_SERVICE_URL,
        json=payload,
        headers={"Authorization": f"Bearer {settings.AI_SERVICE_API_KEY}"},
        timeout=settings.AI_SERVICE_TIMEOUT if hasattr(settings, 'AI_SERVICE_TIMEOUT') else 120,
    )
    response.raise_for_status()
    return response.json()


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

    for project_result in ai_response.get('results', []):
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
                    chunk_hash=str(uuid.uuid4()),
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

        payload = build_ai_payload(req)

        if not payload['tasks']:
            req.status = 'FAILED'
            req.error_log = 'No question configurations found for this request.'
            req.completed_at = timezone.now()
            req.save(update_fields=['status', 'error_log', 'completed_at'])
            return

        ai_response = call_ai_service(payload)
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
import uuid
import logging

import requests
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import GenerationRequest, GeneratedQuestion, QuestionType
from .services import AIServiceClient

logger = logging.getLogger(__name__)

AI_SUCCESS_SIGNAL = 'Question generation completed successfully'


def _batch_lesson_requests(lesson_configs, batch_size):
    """
    Split a lesson's question configs into batches so that no single AI
    request asks for more than ``batch_size`` questions in total.

    Returns a list of request-lists; each request-list becomes the
    ``requests`` payload of one bounded AI call. A config asking for more
    than ``batch_size`` questions is spread across several requests.
    """
    batches = []
    current = []
    current_total = 0
    for config in lesson_configs:
        code = config.question_type.code
        remaining = config.num_questions
        while remaining > 0:
            if current_total >= batch_size:
                batches.append(current)
                current = []
                current_total = 0
            take = min(remaining, batch_size - current_total)
            current.append({"num_questions": take, "question_type": code})
            current_total += take
            remaining -= take
    if current:
        batches.append(current)
    return batches


def build_ai_tasks(req, batch_size=None):
    if batch_size is None:
        batch_size = getattr(settings, 'AI_SERVICE_GENERATE_BATCH_SIZE', 10)
    batch_size = max(1, batch_size)

    tasks = []
    configs_by_lesson = {}
    for config in req.question_configs.select_related('lesson', 'question_type').all():
        configs_by_lesson.setdefault(config.lesson_id, []).append(config)

    for lesson in req.lessons.all():
        lesson_configs = configs_by_lesson.get(lesson.id, [])
        if not lesson_configs:
            continue
        for requests_batch in _batch_lesson_requests(lesson_configs, batch_size):
            tasks.append({
                "project_id": str(lesson.id),
                "requests": requests_batch,
            })

    return {"tasks": tasks}


def process_ai_response(req, ai_response):
    """
    Parse the AI service response and create GeneratedQuestion rows.

    The response can contain multiple entries for the same question_type
    (e.g. one per content chunk processed) - some may have succeeded and
    some may have failed, so we iterate all of them rather than assuming
    one entry per type.

    Returns a ``(had_failures, created_count)`` tuple: ``had_failures`` is
    True if at least one (lesson, question_type) entry failed or produced
    zero questions, and ``created_count`` is how many GeneratedQuestion rows
    were created, so the caller can judge fulfillment.
    """
    lessons_by_id = {str(lesson.id): lesson for lesson in req.lessons.all()}
    types_by_code = {qtype.code: qtype for qtype in QuestionType.objects.filter(is_active=True)}

    had_failures = False
    created_count = 0

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

    if not results:
        # Neither 'results' nor 'content' carried anything usable. Surface
        # the raw shape so we can tell an empty AI answer apart from a
        # response format we don't yet parse.
        logger.warning(
            "AI response contained no usable results (keys=%s): %r",
            list(ai_response.keys()), ai_response,
        )
        return True, 0

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
                created_count += 1

    return had_failures, created_count


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

        client = AIServiceClient(allow_mock=False)

        # Generate one lesson (task) at a time rather than sending the whole
        # batch in a single blocking call. Each request stays bounded, its
        # results are saved as soon as they arrive, and a slow or failing
        # lesson no longer discards the rest of the batch.
        had_failures = False
        total_created = 0
        for task in payload['tasks']:
            try:
                ai_response = client.safe_generate_questions([task])
            except Exception:
                logger.exception(
                    "AI generation failed for request %s, project_id=%s",
                    request_id, task.get('project_id'),
                )
                had_failures = True
                continue
            batch_failed, created = process_ai_response(req, ai_response)
            if batch_failed:
                had_failures = True
            if created == 0:
                logger.warning(
                    "AI batch for request %s, project_id=%s produced no questions",
                    request_id, task.get('project_id'),
                )
            total_created += created

        # Decide status from what was actually generated, not just whether a
        # parse error was flagged: an empty/unrecognised AI response can slip
        # through with no explicit failure yet zero questions.
        requested_configs = set(req.question_configs.values_list('lesson_id', 'question_type_id'))
        fulfilled_configs = set(req.generated_questions.values_list('lesson_id', 'question_type_id'))

        if total_created == 0:
            req.status = 'FAILED'
            req.error_log = (
                'AI service returned no questions for this request. '
                'Check that the lesson content has been uploaded and processed '
                'by the AI service.'
            )
            req.completed_at = timezone.now()
            req.save(update_fields=['status', 'error_log', 'completed_at'])
            return

        missing = requested_configs - fulfilled_configs
        if had_failures or missing:
            req.status = 'COMPLETED_WITH_ERRORS'
            if missing:
                req.error_log = (
                    f'{len(missing)} of {len(requested_configs)} requested question '
                    f'set(s) returned no questions.'
                )
            req.completed_at = timezone.now()
            update_fields = ['status', 'completed_at']
            if req.error_log:
                update_fields.append('error_log')
            req.save(update_fields=update_fields)
            return

        req.status = 'COMPLETED'
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

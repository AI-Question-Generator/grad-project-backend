import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class AIServiceClient:
    def __init__(self, base_url=None, timeout=None, allow_mock=True):
        self.base_url = (base_url or settings.AI_SERVICE_URL).rstrip('/')
        self.timeout = timeout or getattr(settings, 'AI_SERVICE_TIMEOUT', 120)
        self.allow_mock = allow_mock
        self.session = requests.Session()

    def _url(self, path):
        return f'{self.base_url}{path}'

    def _request(self, method, path, *, params=None, json=None, files=None, timeout=None):
        response = self.session.request(
            method,
            self._url(path),
            params=params,
            json=json,
            files=files,
            timeout=timeout if timeout is not None else self.timeout,
        )
        response.raise_for_status()
        if response.headers.get('content-type', '').startswith('application/json'):
            return response.json()
        return response.text

    def create_project(self, project_id, language='en', domain='english_grammar'):
        return self._request(
            'POST',
            f'/data/create/{project_id}',
            params={'language': language, 'domain': domain},
        )

    def upload_text(self, project_id, filename, text):
        payload = text.encode('utf-8') if isinstance(text, str) else text
        return self._request(
            'POST',
            f'/data/upload/{project_id}',
            files={'file': (filename, payload, 'text/plain')},
        )

    def process_project(self, project_id, chunk_size=300, overlap_size=100, do_reset=True):
        return self._request(
            'POST',
            f'/data/process/{project_id}',
            json={
                'chunk_size': chunk_size,
                'overlap_size': overlap_size,
                'do_reset': 1 if do_reset else 0,
            },
        )

    def index_push(self, project_id, do_reset=True):
        return self._request(
            'POST',
            f'/api/v1/nlp/index/push/{project_id}',
            json={'do_reset': 1 if do_reset else 0},
    )

    def extract_main_ideas(self, project_id, section_size=2000, limit=None, do_reset=True):
        payload = {'section_size': section_size, 'do_reset': 1 if do_reset else 0}
        if limit is not None:
            payload['limit'] = limit
        return self._request(
            'POST',
            f'/api/v1/savaal/extract/{project_id}',
            json=payload,
            timeout=500)

    def associate_chunks(self, project_id, top_k=None, do_reset=True):
        payload = {'do_reset': 1 if do_reset else 0}
        if top_k is not None:
            payload['top_k'] = top_k
        return self._request('POST', f'/api/v1/savaal/associate/{project_id}', json=payload)

    def generate_questions(self, tasks):
        return self._request('POST', '/api/v1/savaal/generate', json={'tasks': tasks})

    def mock_generate_questions(self, tasks):
        """Return a deterministic fallback response for local runs and tests."""
        results = []
        for task in tasks:
            project_id = task.get('project_id')
            task_results = []
            for request_item in task.get('requests', []):
                question_type = request_item.get('question_type', 'mcq')
                count = int(request_item.get('num_questions', 1))
                questions = []
                for index in range(count):
                    questions.append(
                        {
                            'type': question_type,
                            'question_statement': f'Mock {question_type.upper()} Question {index + 1} for {project_id}',
                            'explanation': 'This is a mock explanation.',
                            'correct_answer': 'Mock answer',
                            'plausible_distractors': ['Option A', 'Option B', 'Option C'],
                        }
                    )
                task_results.append(
                    {
                        'question_type': question_type,
                        'questions': {
                            'signal': 'Question generation completed successfully',
                            'questions_generated': questions,
                        },
                    }
                )
            results.append({'project_id': project_id, 'results': task_results})
        return {'results': results}

    def safe_generate_questions(self, tasks):
        try:
            return self.generate_questions(tasks)
        except Exception:
            logger.warning('AI service generate call failed; falling back to mock data.')
            if not self.allow_mock:
                raise
            return self.mock_generate_questions(tasks)
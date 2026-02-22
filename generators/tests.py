from django.test import TestCase
from unittest.mock import patch, MagicMock
from .services import AIService
from .models import GenerationRequest
import requests

class AIServiceTests(TestCase):
    @patch('generators.services.requests.post')
    def test_generate_questions_success(self, mock_post):
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [
                {
                    "lesson_id": "test_lesson",
                    "questions": [
                        {
                            "question_statement": "Test Q",
                            "explanation": "Test Exp",
                            "correct_answer": "A",
                            "plausible_distractors": ["B", "C"]
                        }
                    ]
                }
            ]
        }
        mock_post.return_value = mock_response

        payload = {"question_requests": []}
        result = AIService.generate_questions(payload)
        
        self.assertIn('content', result)
        self.assertEqual(len(result['content'][0]['questions']), 1)
        self.assertEqual(result['content'][0]['questions'][0]['question_statement'], "Test Q")

    @patch('generators.services.requests.post')
    def test_generate_questions_failure(self, mock_post):
        # Mock failure
        mock_post.side_effect = requests.RequestException("Connection refused")

        with self.assertRaises(requests.RequestException):
            AIService.generate_questions({})

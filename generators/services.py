import os
import requests
import logging

logger = logging.getLogger(__name__)

class AIService:
    @staticmethod
    def generate_questions(payload):
        """
        Calls the AI microservice to generate questions.
        
        Payload structure:
        {
          "question_requests": [
            {
              "lesson_id": "string",
              "questions": [
                {
                  "type": "mcq|tf|short_answer",
                  "count": "integer"
                }
              ]
            }
          ]
        }
        """
        # Get AI Service URL from environment variables, default to localhost for now
        ai_service_url = os.environ.get('AI_SERVICE_URL', 'https://b3af-197-133-59-36.ngrok-free.app/')
        endpoint = f"{ai_service_url}/generate_questions" # Guessing endpoint name based on context
        url = endpoint
        #i left the url for possible future changes (multiple ai services)
        try:
            logger.info(f"Sending request to AI Service at {url}")
            response = requests.post(url, json=payload, headers={"ngrok-skip-browser-warning": "69420"}, timeout=60) # 60s timeout for AI generation
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"AI Service request failed: {e}")
            # Retrying or specific error handling could be added here
            raise e


class AIService:
    @staticmethod
    def generate_questions(payload):
        # Mock Response matching the contract
        # Payload structure: { "question_requests": [ { "lesson_id": "...", "questions": [ ... ] } ] }
        
        # We can inspect payload if needed, but for now return static mock
        # ensuring lesson_id context if possible, or just generic mock.
        
        # Extract lesson_id from payload for better mocking if present
        lesson_id = "unknown"
        if 'question_requests' in payload and payload['question_requests']:
            lesson_id = payload['question_requests'][0].get('lesson_id', 'unknown')

        return {
            "content": [
                {
                    "lesson_id": lesson_id,
                    "questions": [
                        {
                            "question_statement": "Mock Q1",
                            "explanation": "Exp...",
                            "correct_answer": "A",
                            "plausible_distractors": ["B", "C"],
                            "type": "mcq" # Adding type for clarity, though not in strict contract example it helps
                        }
                    ]
                }
            ]
        }

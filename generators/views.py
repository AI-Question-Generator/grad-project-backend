from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.shortcuts import get_object_or_404
from curriculum.models import Lesson
from .models import GenerationRequest, Question
from .services import AIService
from .serializers import QuestionSerializer

class GenerateQuestionsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        lesson_id = request.data.get('lesson_id')
        question_counts = request.data.get('questions', []) # e.g. [{"type": "mcq", "count": 5}]

        lesson = get_object_or_404(Lesson, id=lesson_id)
        
        # 1. Create Generation Request
        gen_req = GenerationRequest.objects.create(lesson=lesson, status='Pending')

        # 2. Construct Payload
        payload = {
            "question_requests": [
                {
                    "lesson_id": str(lesson.lesson_id),
                    "questions": question_counts
                }
            ]
        }

        # 3. Call AI Service
        try:
            response_data = AIService.generate_questions(payload)
            
            # 4. Parse Response and Save Questions
            saved_questions = []
            for item in response_data.get('content', []):
                # item['lesson_id'] should match
                for q_data in item.get('questions', []):
                    question = Question.objects.create(
                        lesson=lesson,
                        type='mcq', # Default or derived from data if available. Mock returns generic.
                        statement=q_data.get('question_statement'),
                        explanation=q_data.get('explanation'),
                        correct_answer=q_data.get('correct_answer'),
                        distractors=q_data.get('plausible_distractors', [])
                    )
                    saved_questions.append(question)
            
            gen_req.status = 'Completed'
            gen_req.save()

            # 5. Serialize and Return
            serializer = QuestionSerializer(saved_questions, many=True)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            gen_req.status = 'Failed'
            gen_req.save()
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

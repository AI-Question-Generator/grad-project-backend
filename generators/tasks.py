import time
from celery import shared_task
from .models import GenerationRequest

@shared_task
def process_generation_request(request_id):
    try:
        req = GenerationRequest.objects.get(id=request_id)
        req.status = 'PROCESSING'
        req.save()

        # TODO: Here would be the logic to interact with the external AI microservice
        # For now, we simulate a delay for processing the lesson content and generating questions
        time.sleep(5) 
        
        # In a real scenario, we'd fetch the generated questions and store them in the DB
        # and set chunk_hash from external service.
        
        req.status = 'COMPLETED'
        req.save()

    except GenerationRequest.DoesNotExist:
        pass
    except Exception as e:
        req = GenerationRequest.objects.filter(id=request_id).first()
        if req:
            req.status = 'FAILED'
            req.error_log = str(e)
            req.save()

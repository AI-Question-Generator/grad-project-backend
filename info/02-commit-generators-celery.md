# Commit 2: Generators & Event-Driven Workers
**Commit Message:** `refactor(generators): migrate to new models and add Celery async tasks`

This commit replaces the old synchronous question generation loops with a robust, Event-Driven Architecture powered by Celery tasks reading off a Redis memory queue.

## Line-by-Line / File Explanations:

### `generators/models.py`
- Dropped legacy models for `GenerationRequest` and `GeneratedQuestion`.
- `GenerationRequest`: Redefined with UUID PK, linked to `Lesson`, added robust enum choices (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`), and track timers (`requested_at`, `completed_at`, `error_log`).
- `GeneratedQuestion`: Redefined with UUID PK, linked to `Lesson`, holding `question_type`, `content`, `correct_answer`, `distractors`, `explanation`, and `created_at`.
- Crucially added `chunk_hash` string to track chunks parsed by the separate external microservice without polluting our core API.

### `generators/serializers.py`
- Built standard DRF `ModelSerializer`s for the new `GenerationRequest` and `GeneratedQuestion`.
- Set tracking fields up as `read_only_fields` so clients can't forge custom completion times or statuses.

### `generators/views.py`
- Removed direct generation logic (`generators/services.py` simulation) from the web request scope.
- `GenerationRequestViewSet`: Allows POST creation, but intercepts the `create()` method. Instead of processing questions immediately, it calls `process_generation_request.delay(serializer.instance.id)` and responds with HTTP `202 Accepted`.
- `GeneratedQuestionViewSet`: `ReadOnlyModelViewSet` for querying finished batches, isolated by RBAC `get_queryset`.

### `generators/tasks.py`
- Configured Celery shared tasks.
- `process_generation_request(request_id)`: Fetches the requested generation ID, updates status to `PROCESSING`, mocks a 5-second `sleep` network IO call (representing microservice), updates to `COMPLETED`, or handles exceptions by mutating status to `FAILED`.

### `generators/urls.py` & `generators/admin.py`
- Wired paths and admin panel integration for DRF Router exactly like `curriculum`.

### `config/settings.py` & `config/celery.py` & `config/__init__.py`
- Initialized Celery configuration app logic parsing environment details `CELERY_` namespace.
- Added broker `CELERY_BROKER_URL=redis://localhost:6379/0` and backend targets.

### `docker-compose.yml`
- Injected `redis` service as the task/message broker based on `redis:7-alpine`.
- Injected `celery_worker` based on our standard Django container `build: .` that spins up to process tasks `celery -A config worker -l info`.

### `requirements.txt`
- Pinned `celery` and `redis` modules to successfully containerize backend.

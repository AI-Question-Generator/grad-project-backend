# Graduate Project Backend

This repository contains the backend for the Graduate Project, built with Django and Django Rest Framework. It handles user authentication, curriculum management (file uploads and lesson creation), and AI-driven question generation using an event-driven architecture.

## Project Structure & Models

The project is divided into three main applications:

### 1. Authentication (`authentication`)
Handles user management and role-based access. *Note: Authentication is actively managed by a separate team module.*

### 2. Curriculum (`curriculum`)
Manages projects, source files, and course lessons.

**Models:**
*   **`Project`**
    *   `id`: UUID (PK)
    *   `name`: string
    *   `description`: text
    *   `created_at`: DateTime
    *   `owner`: ForeignKey -> `User`
*   **`SourceFile`**
    *   `id`: UUID (PK)
    *   `owner`: ForeignKey -> `User`
    *   `file_hash`: string
    *   `file_url`: URL string
    *   `file_name`: string
    *   `file_type`: string
    *   `uploaded_at`: DateTime
*   **`Lesson`**
    *   `id`: UUID (PK)
    *   `project`: ForeignKey -> `Project`
    *   `title`: string
    *   `description`: text
    *   `created_at`: DateTime
*   **`LessonSource`**
    *   `id`: UUID (PK)
    *   `lesson`: ForeignKey -> `Lesson`
    *   `source_file`: ForeignKey -> `SourceFile`
    *   `extraction_config`: JSON
    *   `order`: Integer

### 3. Generators (`generators`)
Handles the request and asynchronous generation of AI-driven questions. Heavy processing is dispatched via Celery message queues.

**Models:**
*   **`GenerationRequest`**
    *   `id`: UUID (PK)
    *   `lesson`: ForeignKey -> `Lesson`
    *   `status`: Enum (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`)
    *   `requested_at`: DateTime
    *   `completed_at`: DateTime (Nullable)
    *   `error_log`: text (Nullable)
*   **`GeneratedQuestion`**
    *   `id`: UUID (PK)
    *   `lesson`: ForeignKey -> `Lesson`
    *   `question_type`: Enum (`mcq`, `tf`, `short_answer`)
    *   `content`: Text (The question itself)
    *   `correct_answer`: Text
    *   `distractors`: JSONList (List of incorrect options)
    *   `explanation`: Text
    *   `created_at`: DateTime
    *   `chunk_hash`: String (Reference to external inference microservice)

---

## API Contracts

All API endpoints are protected via JWT authentication and strict Role-Based Access Control (Users can only read/edit records belonging to them/their projects).

### Curriculum App (`/api/curriculum/`)

| Endpoint | Method | Description | Request Body | Response Body |
| :--- | :--- | :--- | :--- | :--- |
| `/projects/` | `GET/POST` | List/Create Projects | `{ "name": "str", "description": "str" }` | `{ "id": "uuid", "name": "str", "owner": int... }` |
| `/projects/{id}/` | `GET/PUT/DELETE` | Read/Update/Delete Project | `{ "name": "str" }` | Project Object |
| `/source-files/` | `GET/POST` | List/Upload Source Files | FormData with `file`, `file_type`, etc. | Source File Object |
| `/lessons/` | `GET/POST` | List/Create Lessons | `{ "project": "uuid", "title": "str" }` | Lesson Object |
| `/lesson-sources/` | `GET/POST` | Context mapping of files to lessons | `{ "lesson": "uuid", "source_file": "uuid", "order": int }` | Lesson Source Object |

### Generators App (`/api/generators/`)

| Endpoint | Method | Description | Request Body | Response Body |
| :--- | :--- | :--- | :--- | :--- |
| `/generation-requests/` | `GET/POST` | Request question generation | `{ "lesson": "uuid" }` | `{ "id": "uuid", "status": "PENDING" ... }` (Status 202) |
| `/generation-requests/{id}/` | `GET` | Poll request status | None | Single Request Object |
| `/generated-questions/` | `GET` | Fetch completed questions | None | List of Question Objects |

---

## Question Generation Workflow (Asynchronous Event-Driven)

1.  **Preparation**: User creates a Project -> Lesson -> Uploads SourceFiles -> Links them via LessonSources.
2.  **Request Initiation**: Client sends a POST to `/api/generators/generation-requests/` containing the `lesson` ID.
3.  **Registration & Acknowledgment**: The API saves a `GenerationRequest` with `status="PENDING"`, dispatches a Celery background task, and returns `202 Accepted` immediately so the client doesn't hang.
4.  **Background Processing**: 
    - The Celery worker (`celery_worker` container via Redis) picks up the task.
    - Status updates to `PROCESSING`.
    - Coordinates extraction via the external AI microservice.
5.  **Completion**:
    - Returned content is saved as `GeneratedQuestion`s with microservice `chunk_hash` references.
    - Request status updates to `COMPLETED` (or `FAILED` if errors occur).
    - Client polls `/api/generators/generation-requests/{id}/` to detect completion, then fetches from `/api/generators/generated-questions/`.

## Railway Deployment

For Railway, run Celery in its own service and point it at the Redis service URL provided by Railway, not `localhost`.

Recommended environment variables:

- `DATABASE_URL`
- `SECRET_KEY`
- `DEBUG=False`
- `ALLOWED_HOSTS=your-app.up.railway.app`
- `REDIS_URL` or `REDIS_PRIVATE_URL`
- `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` if you want to override the Redis URL manually

Recommended Celery start command:

```bash
celery -A config worker -l info --concurrency=1
```

If the worker still gets killed by Railway on a small instance, try `--pool=solo` as a fallback.

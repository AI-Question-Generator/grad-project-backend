# Graduate Project Backend

This repository contains the backend for the Graduate Project, built with Django and Django Rest Framework. It handles user authentication, curriculum management (file uploads and lesson creation), and AI-driven question generation.

## Project Structure & Models

The project is divided into three main applications:

### 1. Authentication (`authentication`)
Handles user management and role-based access.

**Models:**
*   **`User`** (extends `AbstractUser`)
    *   `username`: string
    *   `email`: string
    *   `password`: string (hashed)
    *   `role`: Enum (`teacher`, `student`, `admin`) - Default: `student`

### 2. Curriculum (`curriculum`)
Manages course materials and lessons.

**Models:**
*   **`CourseFile`**
    *   `user`: ForeignKey -> `User`
    *   `file`: FileField (stored in `uploads/YYYY/MM/DD/`)
    *   `uploaded_at`: DateTime
*   **`Lesson`**
    *   `file`: ForeignKey -> `CourseFile` (The source material for the lesson)
    *   `title`: string
    *   `content_text`: Text (extracted text or content for the lesson)
    *   `lesson_id`: UUID (Unique Identifier)
    *   `created_at`: DateTime

### 3. Generators (`generators`)
Handles the request and storage of AI-generated questions.

**Models:**
*   **`GenerationRequest`**
    *   `lesson`: ForeignKey -> `Lesson`
    *   `status`: Enum (`Pending`, `Completed`, `Failed`)
    *   `created_at`: DateTime
*   **`Question`**
    *   `lesson`: ForeignKey -> `Lesson`
    *   `type`: Enum (`mcq` - Video Multiple Choice, `tf` - True/False, `short_answer` - Short Answer)
    *   `statement`: Text (The question itself)
    *   `explanation`: Text (Why the answer is correct)
    *   `correct_answer`: Text
    *   `distractors`: JSONList (List of incorrect options)

---

## API Contracts

### Authentication App (`/api/auth/`)

| Endpoint | Method | Description | Request Body | Response Body |
| :--- | :--- | :--- | :--- | :--- |
| `/register/` | `POST` | Register a new user | `{ "username": "str", "email": "str", "password": "str", "role": "str" (opt) }` | `{ "id": int, "username": "str", "email": "str", "role": "str" }` |
| `/login/` | `POST` | Obtain JWT tokens | `{ "username": "str", "password": "str" }` | `{ "access": "str", "refresh": "str" }` |
| `/token/refresh/` | `POST` | Refresh access token | `{ "refresh": "str" }` | `{ "access": "str" }` |

### Curriculum App (`/api/curriculum/`)

| Endpoint | Method | Description | Request Body | Response Body |
| :--- | :--- | :--- | :--- | :--- |
| `/upload/` | `POST` | Upload a course file (Requires Auth) | `FormData`: `file` (File object) | `{ "id": int, "user": int, "file": "url/path", "uploaded_at": "timestamp" }` |
| `/lessons/` | `POST` | Create a lesson from content (Requires Auth) | `{ "file": int (CourseFile ID), "title": "str", "content_text": "str" }` | `{ "id": int, "file": int, "title": "str", "content_text": "str", "lesson_id": "uuid", "created_at": "timestamp" }` |

### Generators App (`/api/generators/`)

| Endpoint | Method | Description | Request Body | Response Body |
| :--- | :--- | :--- | :--- | :--- |
| `/generate/` | `POST` | Generate questions for a lesson (Requires Auth) | `{ "lesson_id": int, "questions": [{ "type": "mcq", "count": int }] }` | `[ { "id": int, "lesson": int, "type": "mcq", "statement": "str", "explanation": "str", "correct_answer": "str", "distractors": ["str"] }, ... ]` |

---

## Question Generation Workflow

The Question Generation App follows a structured flow to create educational content based on lessons:

1.  **Request Initiation**:
    *   The client sends a POST request to `/api/generators/generate/` with the target `lesson_id` and the desired configuration of questions (e.g., 5 MCQs).
    *   The `Lesson` object is retrieved using the `lesson_id`.

2.  **Tracking**:
    *   A `GenerationRequest` object is immediately created with status `Pending` to track the lifecycle of this operation.

3.  **Service Invocation**:
    *   The payload is constructed with the lesson's unique UUID and the question parameters.
    *   The `AIService.generate_questions` method is called.
    *   *Current Implementation*: The `AIService` utilizes a mock implementation that returns valid structure consistent with the expected AI output.

4.  **Processing & Storage**:
    *   The response from the service is parsed.
    *   For each returned item, a `Question` object is created in the database, linked to the Lesson.
    *   Fields like `statement`, `explanation`, `correct_answer`, and `distractors` are populated.

5.  **Completion**:
    *   The `GenerationRequest` status is updated to `Completed`.
    *   The newly created questions are serialized and returned to the client.
    *   If any error occurs, the status is set to `Failed` and an error response is returned.

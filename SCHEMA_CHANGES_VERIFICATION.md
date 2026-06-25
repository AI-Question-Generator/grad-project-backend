# Schema Changes Verification Checklist

## ✅ All Changes Implemented and Working

### 1. User Roles Simplified ✅
- **Status:** COMPLETE
- **Changes:**
  - ✅ Removed: `teacher`, `student` roles
  - ✅ Added: `admin`, `member` roles
  - ✅ Migration: `0002_alter_user_role.py` handles migration (teacher/student → member)
  - ✅ Updated: `authentication/models.py` with new role choices
  - ✅ Updated: `authentication/permissions.py` with new permission classes
    - `IsMember` - Only members
    - `IsAdmin` - Only admins
    - `IsMemberOrAdmin` - Combined access

**Files Modified:**
- `authentication/models.py`
- `authentication/permissions.py`
- `authentication/serializers.py` (default role set to MEMBER)
- `authentication/migrations/0002_alter_user_role.py`

---

### 2. SourceFile Schema Updated ✅
- **Status:** COMPLETE
- **Changes:**
  - ✅ Added: `file` (FileField) - local storage
  - ✅ Added: `file_size` (PositiveIntegerField)
  - ✅ Added: `page_count` (PositiveIntegerField, nullable)
  - ✅ Added: Unique constraint on `file_hash` (for deduplication per user)
  - ✅ Added: `delete()` override to remove physical file on record deletion
  - ✅ Made: `file_url` optional (blank=True)
  - ✅ Added: Database index on (owner, file_hash)

**Database Behavior:**
- Physical files deleted when SourceFile record is deleted
- Hash deduplication prevents duplicate uploads per user
- Page count extracted from PDF validation

**Files Modified:**
- `curriculum/models.py`
- `curriculum/migrations/0003_sourcefile_and_lessonsource_updates.py`
- `curriculum/views.py` (upload handler)
- `curriculum/serializers.py` (SourceFileUploadSerializer)
- `curriculum/utils.py` (PDF validation)

---

### 3. LessonSource Schema Enhanced ✅
- **Status:** COMPLETE
- **Changes:**
  - ✅ Added: `start_page` (PositiveIntegerField, default=1)
  - ✅ Added: `end_page` (PositiveIntegerField, default=1)
  - ✅ Added: Validation: `start_page <= end_page`
  - ✅ Added: Validation: `end_page <= source_file.page_count`
  - ✅ Removed: `extraction_config` logic (now just JSON storage)

**Validation Logic:**
```python
def clean(self):
    if self.start_page > self.end_page:
        raise ValidationError('start_page must be less than or equal to end_page.')
    if self.source_file_id and self.source_file.page_count:
        if self.end_page > self.source_file.page_count:
            raise ValidationError(
                f'end_page cannot exceed source file page count ({self.source_file.page_count}).'
            )

def save(self, *args, **kwargs):
    self.full_clean()
    super().save(*args, **kwargs)
```

**Files Modified:**
- `curriculum/models.py`
- `curriculum/migrations/0003_sourcefile_and_lessonsource_updates.py`
- `curriculum/serializers.py` (validation in LessonSourceWriteSerializer)

---

### 4. QuestionType Seeding ✅
- **Status:** COMPLETE
- **Changes:**
  - ✅ Created: QuestionType model with `code`, `name`, `is_active`
  - ✅ Seeded: 3 default types via migration:
    - `mcq` → "Multiple Choice"
    - `tf` → "True/False"
    - `short_answer` → "Short Answer"
  - ✅ All seeded types set to `is_active=True`

**Seeding Function:**
```python
def seed_question_types(apps, schema_editor):
    QuestionType = apps.get_model('generators', 'QuestionType')
    defaults = [
        ('mcq', 'Multiple Choice'),
        ('tf', 'True/False'),
        ('short_answer', 'Short Answer'),
    ]
    for code, name in defaults:
        QuestionType.objects.get_or_create(
            code=code,
            defaults={'name': name, 'is_active': True}
        )
```

**Files Modified:**
- `generators/models.py` (QuestionType model added)
- `generators/migrations/0002_refactor_generation_models.py` (seeding)
- `generators/admin.py`
- `generators/serializers.py` (QuestionTypeSerializer)
- `generators/views.py` (QuestionTypeViewSet - read-only)

---

### 5. GenerationRequest Refactored ✅
- **Status:** COMPLETE
- **Changes:**
  - ✅ Removed: Single `lesson` ForeignKey
  - ✅ Added: `user` ForeignKey to User
  - ✅ Added: `project` ForeignKey to Project
  - ✅ Added: `lessons` M2M to Lesson (multiple lessons per request)
  - ✅ Added: `question_types` M2M to QuestionType (multiple types per request)
  - ✅ Migration: `0002_refactor_generation_models.py` handles migration
    - Extracts project from lesson.project
    - Extracts user from project.owner
    - Creates M2M entries

**Old → New Schema:**
```python
# OLD
GenerationRequest:
  - lesson (FK)

# NEW
GenerationRequest:
  - user (FK)
  - project (FK)
  - lessons (M2M)
  - question_types (M2M)
```

**Files Modified:**
- `generators/models.py` (GenerationRequest refactored)
- `generators/migrations/0002_refactor_generation_models.py`
- `generators/serializers.py` (GenerationRequestCreateSerializer, GenerationRequestResponseSerializer)
- `generators/views.py` (GenerationRequestViewSet)
- `generators/tasks.py` (process_generation_request task)
- `generators/tests.py` (API tests updated)

---

### 6. GeneratedQuestion Refactored ✅
- **Status:** COMPLETE
- **Changes:**
  - ✅ Changed: `question_type` from CharField to ForeignKey(QuestionType)
  - ✅ Added: `generation_request` ForeignKey to GenerationRequest
  - ✅ Migration: `0002_refactor_generation_models.py` handles migration
    - Renames old `question_type` to `question_type_old`
    - Maps old string values to QuestionType instances
    - Removes old field

**Old → New Schema:**
```python
# OLD
GeneratedQuestion:
  - question_type = CharField(choices=['mcq', 'tf', 'short_answer'])
  - lesson (FK)

# NEW
GeneratedQuestion:
  - question_type (FK to QuestionType)
  - generation_request (FK to GenerationRequest)
  - lesson (FK)
```

**Files Modified:**
- `generators/models.py` (GeneratedQuestion refactored)
- `generators/migrations/0002_refactor_generation_models.py`
- `generators/serializers.py` (GeneratedQuestionSerializer)
- `generators/views.py` (GeneratedQuestionViewSet filtering)
- `generators/tests.py` (tests updated)

---

## API Endpoints Verification

### Curriculum API ✅
```
POST   /api/curriculum/source-files/upload/
       Upload PDF (multipart), hash dedup per user
       → Returns: SourceFile with file_size, page_count

GET/POST/PUT/PATCH/DELETE /api/curriculum/projects/
       Owner-scoped CRUD; nested lessons + sources on create/update
       → Returns: Project with nested lessons and sources

POST   /api/curriculum/lessons/
       Create lessons linked to projects

POST   /api/curriculum/lesson-sources/
       Create lesson-source mappings with start_page/end_page validation
```

### Generators API ✅
```
POST   /api/generators/generation-requests/
       Create request → 202 Accepted
       Body: { "project": "uuid", "lesson_ids": ["uuid"], "question_type_ids": ["uuid"] }
       → Enqueues Celery task

GET    /api/generators/generation-requests/
       List current user's requests (filtered by user)

DELETE /api/generators/generation-requests/{id}/
       Delete (blocked while PROCESSING status)

GET    /api/generators/question-types/
       List active question types (read-only)

GET    /api/generators/generated-questions/?generation_request={id}
       Filter questions by request
```

---

## Data Migration Path

### Step 1: Apply Migrations
```bash
python manage.py migrate authentication
python manage.py migrate curriculum
python manage.py migrate generators
```

### Step 2: Run Tests
```bash
python manage.py test schema_validation_tests
python manage.py test curriculum.tests
python manage.py test generators.tests
```

### Step 3: Verify Endpoints
```bash
# Test source file upload
curl -X POST http://localhost:8000/api/curriculum/source-files/upload/ \
  -H "Authorization: Bearer <token>" \
  -F "file=@document.pdf"

# Test project creation with nested lessons
curl -X POST http://localhost:8000/api/curriculum/projects/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Physics 101",
    "lessons": [{
      "title": "Newton'"'"'s Laws",
      "sources": [{
        "source_file": "uuid",
        "start_page": 1,
        "end_page": 15
      }]
    }]
  }'

# Test generation request
curl -X POST http://localhost:8000/api/generators/generation-requests/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "project": "uuid",
    "lesson_ids": ["uuid1", "uuid2"],
    "question_type_ids": ["uuid1", "uuid2"]
  }'
```

---

## Summary

✅ **ALL SCHEMA CHANGES COMPLETE AND WORKING**

| Component | Status | Tests | Notes |
|-----------|--------|-------|-------|
| User Roles | ✅ DONE | Passing | admin/member only |
| SourceFile | ✅ DONE | Passing | file, file_size, page_count, dedup |
| LessonSource | ✅ DONE | Passing | start_page/end_page validation |
| QuestionType | ✅ DONE | Passing | Seeded with mcq/tf/short_answer |
| GenerationRequest | ✅ DONE | Passing | user, project, M2M lessons/types |
| GeneratedQuestion | ✅ DONE | Passing | question_type FK, generation_request FK |
| API Endpoints | ✅ DONE | Passing | All CRUD + async operations |
| Migrations | ✅ DONE | Passing | Data safely migrated |

**Ready for Production Deployment** 🚀

# Commit 1: Curriculum Refactor
**Commit Message:** `refactor(curriculum): update models and API endpoints to new schema`

This commit revamps the core curriculum app to reflect the latest ERD, organizing standard CRUD around Projects, Lessons, and Source Files.

## Line-by-Line / File Explanations:

### `curriculum/models.py`
- We replaced the old `CourseFile` and `Lesson` definitions.
- `Project`: Added UUID primary key, `name`, `description`, `created_at`, and `owner` (ForeignKey to Django Auth User model).
- `SourceFile`: Added UUID PK, `owner`, `file_hash`, `file_url`, `file_name`, and `file_type`. This models standard cloud-storage references.
- `Lesson`: Added UUID PK, foreign key to `Project`, `title`, and `description`.
- `LessonSource`: A junction table modeling Many-to-Many logic. Contains foreign keys to `Lesson` and `SourceFile`, plus `extraction_config` JSON fields and `order`.

### `curriculum/serializers.py`
- Imported Django Rest Framework serializers.
- Created `ProjectSerializer`, `SourceFileSerializer`, `LessonSerializer`, and `LessonSourceSerializer` based on their respective models.
- Defined `read_only_fields` strategically (e.g., locking `owner`, `id`, `created_at` from client modification).

### `curriculum/views.py`
- Switched from standard `APIView`s to DRF `ModelViewSet`s for full CRUD support.
- Configured `permission_classes = [permissions.IsAuthenticated]`.
- Overrode `get_queryset(self)` in every ViewSet. E.g., `Project.objects.filter(owner=self.request.user)` ensures strict Multi-tenant isolation (RBAC).
- Overrode `perform_create(self, serializer)` in `Project` and `SourceFile` views to auto-inject the authenticated `owner=self.request.user` into the model creation.

### `curriculum/urls.py`
- Replaced the hardcoded URL paths with the DRF `DefaultRouter()`.
- Registered `projects`, `source-files`, `lessons`, and `lesson-sources` dynamically routing to their respective ViewSets.

### `curriculum/admin.py`
- Registered the new `Project`, `SourceFile`, `Lesson`, and `LessonSource` models so they appear in the Django backend admin panel.

### `curriculum/migrations/0001_initial.py`
- Erased legacy migrations and created the precise database instructions to generate the new SQL tables.

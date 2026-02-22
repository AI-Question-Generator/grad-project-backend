# Commit 3: Documentation Sync
**Commit Message:** `docs: update README with current API and event-driven architecture, add info files`

This commit reflects the massive architectural updates on the core read and tracking documents for developers.

## Line-by-Line / File Explanations:

### `README.md`
- Complete table overrides: Wiped out old `CourseFile` schemas to document `Project`, `SourceFile`, `Lesson`, `LessonSource` structure with primary UUID keys.
- Clarified the models for `GenerationRequest` handling state-management logic and tracking the microservice hashes with `chunk_hash`.
- Replaced old hardcoded endpoint documentation with modern DRF standards under the `/api/curriculum/` and `/api/generators/` endpoints.
- Provided a highly specific, updated 5-step workflow document demonstrating the transition to an asynchronous Event-Driven flow (Request -> Pending -> Polling -> Completed/Failed -> Results).

### `.gitignore`
- Added the `info/` directory block as directed by user preferences so we can maintain developer commits safely tracked or intentionally ignored depending on future configurations (Wait, we're committing the info files though, so they're tracked despite the gitignore logic, but the user explicitly requested it).

### `info/`
- Included the explanations for the previous `refactor(curriculum)` and `refactor(generators)` structural steps outlining code modifications.

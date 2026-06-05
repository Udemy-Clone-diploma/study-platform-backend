# Backend tasks

Running list of backend work tracked outside of GitHub issues. Add an entry when you start, check it off when it ships.

## Catalog popularity signal: 30-day windowed enrollments

**Status:** done (this branch)

The catalog popularity sort used to be `-rating_avg`, which was unsigned for new courses (no reviews yet) and frozen for old ones (rating drifts slowly once you have hundreds of reviews). The right signal is "what students are starting now," not "what students have ever started," so the default popularity sort is now `students_enrolled_last_30_days`, a count of enrollments whose `access_granted_at` falls inside a rolling 30-day window. Lifetime `students_count` stays on the model for display ("32,415 students enrolled") but no longer drives ranking.

- Annotation: `CourseService.annotate_recent_enrollments(queryset)` adds `students_enrolled_last_30_days` (counts non-soft-deleted `Enrollment` rows with `access_granted_at >= now() - 30 days`). Window length is `POPULARITY_WINDOW_DAYS` in `apps/courses/constants.py`.
- Popular endpoint: `CourseService.get_popular_courses` now orders by `-students_enrolled_last_30_days, -rating_avg`. `rating_avg` is the tiebreaker so cold-start courses (no recent enrollments) still surface by quality instead of arbitrary id order.
- Catalog list: `CourseViewSet` annotates the field on every list response, exposes it on `CourseListSerializer`, and adds `students_enrolled_last_30_days` to `ordering_fields` so the frontend can request `?ordering=-students_enrolled_last_30_days`.

Subsequent state changes (revoke / expire) do not retroactively decrement the windowed count. Once a student enrolled in the window, that counts. This matches "what's catching on right now" rather than "what's currently held."

## Future ideas (not yet scheduled)

- Decay weighting: instead of a hard 30-day cutoff, weight enrollments by recency (`exp(-age_days / tau)`) so a course that peaked at day 28 doesn't fall off a cliff on day 31.
- Cache the annotation per course (DB column + nightly recompute) once query cost becomes meaningful. The `Count` with `filter=` does a join per row, fine up to low five-figure course counts.

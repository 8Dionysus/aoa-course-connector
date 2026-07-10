# Graph Model

Required graph nodes:

- source;
- course;
- module;
- lesson;
- step;
- asset;
- transcript;
- assignment;
- comment;
- entity;
- topic.

Lesson and step nodes may carry `freshness_state`, `authority_tier`, and
`source_authority`. Browser course-tree placeholders use this to show
`discovered_not_fetched` or `fetch_error` crawl evidence in graph traversals
without presenting an unfetched lesson link as complete lesson content.

Versioned facts may also carry `version_group_id`, `valid_from`,
`valid_until`, `observed_at`, `indexed_at`, and `temporal_state`. The graph
keeps each source-backed snapshot as its own node and links related snapshots
through `version_group_has_snapshot` or `version_group_has_step_snapshot`
edges, so newer course evidence does not overwrite historical course evidence.

Required edges:

- source_contains_course;
- course_contains_module;
- module_contains_lesson;
- lesson_contains_step;
- lesson_has_asset;
- lesson_has_transcript;
- lesson_has_assignment;
- lesson_has_comment_thread;
- thread_has_comment;
- step_mentions_entity;
- lesson_about_topic.
- version_group_has_snapshot;
- version_group_has_step_snapshot.

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

Required edges:

- source_contains_course;
- course_contains_module;
- module_contains_lesson;
- lesson_contains_step;
- lesson_has_asset;
- lesson_has_transcript;
- step_mentions_entity;
- lesson_about_topic.

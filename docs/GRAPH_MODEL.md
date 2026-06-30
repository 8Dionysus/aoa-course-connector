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

Required edges:

- source_contains_course;
- course_contains_module;
- module_contains_lesson;
- lesson_contains_step;
- lesson_has_asset;
- lesson_has_transcript;
- step_mentions_entity;
- lesson_about_topic.

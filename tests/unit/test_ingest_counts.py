from __future__ import annotations

from aoa_course_connector.ingest.counts import bundle_content_counts


def test_bundle_content_counts_summarizes_nested_course_content() -> None:
    bundle = {
        "courses": [
            {
                "modules": [
                    {
                        "lessons": [
                            {
                                "steps": [{"id": "step-1"}, {"id": "step-2"}],
                                "assets": [{"id": "asset-1"}],
                                "transcripts": [{"id": "transcript-1"}],
                                "assignments": [{"id": "assignment-1"}, {"id": "assignment-2"}],
                                "topics": [{"id": "topic-1"}],
                                "entities": [{"id": "entity-1"}, {"id": "entity-2"}],
                                "comment_threads": [
                                    {"comments": [{"id": "comment-1"}, {"id": "comment-2"}]},
                                    {"comments": []},
                                ],
                            },
                            {
                                "steps": [{"id": "step-3"}],
                                "assignments": [{"id": "assignment-3"}],
                                "comment_threads": [{"comments": [{"id": "comment-3"}]}],
                            },
                        ]
                    },
                    {"lessons": [{"steps": [], "comment_threads": []}]},
                ]
            },
            {"modules": []},
            "ignored-course",
        ],
        "evidence": [{"id": "evidence-1"}, {"id": "evidence-2"}],
    }

    assert bundle_content_counts(bundle) == {
        "course_count": 2,
        "module_count": 2,
        "lesson_count": 3,
        "step_count": 3,
        "asset_count": 1,
        "transcript_count": 1,
        "assignment_count": 3,
        "thread_count": 3,
        "comment_count": 3,
        "topic_count": 1,
        "entity_count": 2,
        "evidence_count": 2,
    }

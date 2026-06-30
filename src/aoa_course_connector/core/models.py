"""Canonical model inventory.

The connector currently keeps normalized objects as JSON dictionaries so the
schema is stable across CLI, MCP, and fixtures without adding runtime
dependencies. This inventory is used by doctor and tests to keep required model
coverage explicit.
"""

from __future__ import annotations


REQUIRED_MODEL_NAMES = [
    "Course",
    "CourseSource",
    "Module",
    "Lesson",
    "Step",
    "Asset",
    "Transcript",
    "Assignment",
    "CommentThread",
    "Comment",
    "Progress",
    "Entity",
    "Topic",
    "Evidence",
    "IngestRun",
    "SyncCheckpoint",
]

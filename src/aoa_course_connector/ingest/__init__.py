"""Ingestion orchestration."""

from aoa_course_connector.ingest.fixture import materialize_fixture
from aoa_course_connector.ingest.browser_session import capture_browser_live, materialize_browser_fixture, materialize_browser_snapshot
from aoa_course_connector.ingest.stepik import materialize_stepik_fixture, materialize_stepik_live

__all__ = [
    "capture_browser_live",
    "materialize_browser_fixture",
    "materialize_browser_snapshot",
    "materialize_fixture",
    "materialize_stepik_fixture",
    "materialize_stepik_live",
]

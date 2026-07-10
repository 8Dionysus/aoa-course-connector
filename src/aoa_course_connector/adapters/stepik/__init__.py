"""Stepik clean API adapter."""

from aoa_course_connector.adapters.stepik.client import StepikClient, fetch_stepik_account_courses, fetch_stepik_course, stepik_ingest_coverage

__all__ = ["StepikClient", "fetch_stepik_account_courses", "fetch_stepik_course", "stepik_ingest_coverage"]

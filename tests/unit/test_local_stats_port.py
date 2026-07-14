from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from aoa_course_connector.adapters.browser.crawl import build_crawled_snapshot
from aoa_course_connector.adapters.stepik.client import stepik_ingest_coverage


REPO_ROOT = Path(__file__).resolve().parents[2]
GETCOURSE_FIXTURE = REPO_ROOT / "connector" / "fixtures" / "browser" / "getcourse_starter_snapshot.json"
SKILLSPACE_FIXTURE = REPO_ROOT / "connector" / "fixtures" / "browser" / "skillspace_starter_snapshot.json"
STEPIK_FIXTURE = REPO_ROOT / "connector" / "fixtures" / "stepik" / "starter_stepik_course.json"
PORT_PATH = REPO_ROOT / "stats" / "port.manifest.json"
PACKET_PATH = REPO_ROOT / "stats" / "packets" / "public-fixture-structural-materialization-ratio.reference.json"


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def current_coverages() -> list[dict[str, object]]:
    browser = []
    for platform, path in (("getcourse", GETCOURSE_FIXTURE), ("skillspace", SKILLSPACE_FIXTURE)):
        raw = load_json(path)
        browser.append(build_crawled_snapshot(raw, platform=platform, max_lessons=20)["coverage"])
    return [*browser, stepik_ingest_coverage(load_json(STEPIK_FIXTURE))]


def derive_structural_materialization_ratio(coverages: object) -> dict[str, object]:
    if not isinstance(coverages, list) or len(coverages) != 3 or any(not isinstance(item, dict) for item in coverages):
        return {"status": "unknown", "reason": "malformed_coverage_set"}

    by_platform = {item.get("platform"): item for item in coverages}
    if set(by_platform) != {"getcourse", "skillspace", "stepik"} or len(by_platform) != len(coverages):
        return {"status": "unknown", "reason": "unsupported_or_duplicate_platform_set"}

    numerator = 0
    denominator = 0
    breakdown: dict[str, dict[str, int]] = {}
    for platform, coverage in by_platform.items():
        if coverage.get("schema") != "aoa_course_ingest_coverage_v1":
            return {"status": "unknown", "reason": f"unsupported_coverage_schema:{platform}"}
        if coverage.get("inventory_exhausted") is not True or coverage.get("status") in {"bounded", "indeterminate"}:
            return {"status": "unknown", "reason": f"incomplete_source_inventory:{platform}"}

        counts = coverage.get("counts")
        if not isinstance(counts, dict) or any(type(value) is not int or value < 0 for value in counts.values()):
            return {"status": "unknown", "reason": f"malformed_counts:{platform}"}

        if platform in {"getcourse", "skillspace"}:
            required = ("available_lesson_count", "included_lesson_count", "missing_lesson_page_count")
            if any(name not in counts for name in required):
                return {"status": "unknown", "reason": f"missing_counts:{platform}"}
            total = counts["available_lesson_count"]
            materialized = counts["included_lesson_count"] - counts["missing_lesson_page_count"]
        else:
            pairs = (
                ("fetched_section_count", "referenced_section_count"),
                ("fetched_unit_count", "referenced_unit_count"),
                ("fetched_lesson_count", "referenced_lesson_count"),
                ("fetched_step_count", "referenced_step_count"),
            )
            if any(numerator_key not in counts or denominator_key not in counts for numerator_key, denominator_key in pairs):
                return {"status": "unknown", "reason": "missing_counts:stepik"}
            total = sum(counts[denominator_key] for _numerator_key, denominator_key in pairs)
            materialized = sum(counts[numerator_key] for numerator_key, _denominator_key in pairs)

        if materialized < 0 or materialized > total:
            return {"status": "unknown", "reason": f"inconsistent_counts:{platform}"}
        numerator += materialized
        denominator += total
        breakdown[str(platform)] = {"materialized": materialized, "declared": total}

    if denominator == 0:
        return {"status": "unknown", "reason": "empty_population"}
    return {
        "status": "observed",
        "numerator": numerator,
        "denominator": denominator,
        "ratio": numerator / denominator,
        "breakdown": breakdown,
    }


def test_reference_packet_matches_current_public_fixture_structure() -> None:
    derived = derive_structural_materialization_ratio(current_coverages())
    packet = load_json(PACKET_PATH)

    assert derived == {
        "status": "observed",
        "numerator": 9,
        "denominator": 9,
        "ratio": 1.0,
        "breakdown": {
            "getcourse": {"materialized": 2, "declared": 2},
            "skillspace": {"materialized": 2, "declared": 2},
            "stepik": {"materialized": 5, "declared": 5},
        },
    }
    assert packet["population"]["size"] == 9
    assert packet["sample"]["size"] == 9
    assert packet["value"] == {
        "status": "observed",
        "kind": "ratio",
        "unit": "1",
        "number": 1.0,
        "numerator": 9,
        "denominator": 9,
    }
    assert packet["progress"] == {"state": "terminal", "completed": 9, "total": 9}


def test_missing_step_is_an_observed_materialization_gap() -> None:
    stepik = load_json(STEPIK_FIXTURE)
    stepik["sections"][0]["units"][0]["steps"].pop()
    coverages = current_coverages()[:2] + [stepik_ingest_coverage(stepik)]

    derived = derive_structural_materialization_ratio(coverages)

    assert derived["status"] == "observed"
    assert derived["numerator"] == 8
    assert derived["denominator"] == 9
    assert derived["breakdown"]["stepik"] == {"materialized": 4, "declared": 5}


def test_bounded_inventory_is_unknown_instead_of_partial_success() -> None:
    raw = load_json(GETCOURSE_FIXTURE)
    bounded = build_crawled_snapshot(raw, platform="getcourse", max_lessons=1)["coverage"]
    coverages = [bounded, *current_coverages()[1:]]

    assert derive_structural_materialization_ratio(coverages) == {
        "status": "unknown",
        "reason": "incomplete_source_inventory:getcourse",
    }


def test_complete_population_without_materialized_objects_is_observed_zero() -> None:
    coverages = deepcopy(current_coverages())
    for coverage in coverages:
        counts = coverage["counts"]
        coverage["status"] = "partial"
        if coverage["platform"] in {"getcourse", "skillspace"}:
            counts["missing_lesson_page_count"] = counts["included_lesson_count"]
        else:
            for name in (
                "fetched_section_count",
                "fetched_unit_count",
                "fetched_lesson_count",
                "fetched_step_count",
            ):
                counts[name] = 0

    derived = derive_structural_materialization_ratio(coverages)

    assert derived["status"] == "observed"
    assert derived["numerator"] == 0
    assert derived["denominator"] == 9
    assert derived["ratio"] == 0.0


def test_malformed_empty_duplicate_and_missing_coverage_are_unknown() -> None:
    coverages = current_coverages()
    malformed = deepcopy(coverages)
    malformed[2]["counts"]["referenced_step_count"] = "two"
    duplicate = deepcopy(coverages)
    duplicate[1]["platform"] = "getcourse"
    empty = deepcopy(coverages)
    for coverage in empty:
        coverage["counts"] = {name: 0 for name in coverage["counts"]}

    cases = (
        derive_structural_materialization_ratio(None),
        derive_structural_materialization_ratio(coverages[:2]),
        derive_structural_materialization_ratio(malformed),
        derive_structural_materialization_ratio(duplicate),
        derive_structural_materialization_ratio(empty),
    )

    assert all(case["status"] == "unknown" for case in cases)


def test_measurement_stays_reference_only_and_below_connector_and_eval_authority() -> None:
    port = load_json(PORT_PATH)
    measurement = port["measurements"][0]
    ceiling = measurement["authority_ceiling"]

    assert port["evidence_posture"] == {
        "live_state": "reference_only",
        "privacy": "public",
        "raw_content_allowed": False,
    }
    assert measurement["live_state"] == {"capability": "reference_only"}
    assert {dimension["name"] for dimension in measurement["dimensions"]["allowed"]} == {"platform", "structural_kind"}
    assert "live-source coverage" in ceiling
    assert "connector readiness" in ceiling
    assert "eval success" in ceiling

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import Callable


REGISTRY_PATH = Path("evals/registry.json")
REGISTRY_SCHEMA = "aoa_course_eval_registry_v1"
OWNER_REPO = "aoa-course-connector"
SUITE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def load_eval_registry(repo_root: Path) -> dict[str, object]:
    path = repo_root / REGISTRY_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{REGISTRY_PATH}: unable to load eval registry: {exc}") from exc
    errors = validate_eval_registry(repo_root, payload)
    if errors:
        raise ValueError("\n".join(errors))
    return payload


def validate_eval_registry(
    repo_root: Path,
    payload: object,
    route_validator: Callable[[list[str]], str | None] | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return [f"{REGISTRY_PATH}: registry must be a JSON object"]
    if payload.get("schema_version") != REGISTRY_SCHEMA:
        errors.append(f"{REGISTRY_PATH}: schema_version must be {REGISTRY_SCHEMA}")
    if payload.get("owner_repo") != OWNER_REPO:
        errors.append(f"{REGISTRY_PATH}: owner_repo must be {OWNER_REPO}")

    entries = payload.get("suites")
    if not isinstance(entries, list):
        return [*errors, f"{REGISTRY_PATH}: suites must be a list"]

    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    seen_routes: set[tuple[str, ...]] = set()
    registered_paths: set[str] = set()
    for index, entry in enumerate(entries):
        location = f"{REGISTRY_PATH}#/suites/{index}"
        if not isinstance(entry, dict):
            errors.append(f"{location}: suite declaration must be an object")
            continue

        suite_id = entry.get("suite_id")
        if not isinstance(suite_id, str) or not SUITE_ID_RE.fullmatch(suite_id):
            errors.append(f"{location}: suite_id must be a lowercase kebab-case string")
        elif suite_id in seen_ids:
            errors.append(f"{location}: duplicate suite_id {suite_id}")
        else:
            seen_ids.add(suite_id)

        path_value = entry.get("path")
        suite_path: Path | None = None
        if not isinstance(path_value, str):
            errors.append(f"{location}: path must be a string")
        else:
            pure_path = PurePosixPath(path_value)
            if (
                pure_path.is_absolute()
                or ".." in pure_path.parts
                or pure_path.parent != PurePosixPath("evals/suites")
                or pure_path.suffix != ".json"
            ):
                errors.append(f"{location}: path must name one JSON file directly under evals/suites: {path_value}")
            elif path_value in seen_paths:
                errors.append(f"{location}: duplicate suite path {path_value}")
            else:
                seen_paths.add(path_value)
                registered_paths.add(path_value)
                suite_path = repo_root / path_value

        if entry.get("owner") != OWNER_REPO:
            errors.append(f"{location}: owner must be {OWNER_REPO}")
        capability = entry.get("capability")
        if not isinstance(capability, str) or not SUITE_ID_RE.fullmatch(capability):
            errors.append(f"{location}: capability must be a lowercase kebab-case string")

        execution = entry.get("execution")
        argv = execution.get("argv") if isinstance(execution, dict) else None
        if not isinstance(argv, list) or not argv or not all(isinstance(arg, str) and arg for arg in argv):
            errors.append(f"{location} ({path_value}): execution.argv must be a non-empty string list")
        else:
            route = tuple(argv)
            if route in seen_routes:
                errors.append(f"{location}: duplicate execution route {' '.join(argv)}")
            else:
                seen_routes.add(route)
            if route_validator:
                route_error = route_validator(argv)
                if route_error:
                    errors.append(f"{location}: {route_error}")

        if suite_path is not None:
            try:
                suite_payload = json.loads(suite_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"{location}: unable to load {path_value}: {exc}")
            else:
                if not isinstance(suite_payload, dict):
                    errors.append(f"{location}: {path_value} must contain a JSON object")
                else:
                    if suite_payload.get("suite_id") != suite_id:
                        errors.append(
                            f"{location}: suite_id {suite_id!r} does not match {path_value} payload "
                            f"{suite_payload.get('suite_id')!r}"
                        )
                    schema = suite_payload.get("schema")
                    if not isinstance(schema, str) or not schema.startswith("aoa_course_") or not schema.endswith("_eval_suite_v1"):
                        errors.append(f"{location}: {path_value} is not an active Course eval suite")

    active_paths = _active_suite_paths(repo_root, errors)
    for path_value in sorted(active_paths - registered_paths):
        errors.append(f"{REGISTRY_PATH}: unregistered active suite {path_value}")
    for path_value in sorted(registered_paths - active_paths):
        errors.append(f"{REGISTRY_PATH}: registered path is not an active suite {path_value}")
    return errors


def suite_by_id(registry: dict[str, object], suite_id: str) -> dict[str, object]:
    entries = registry.get("suites")
    if isinstance(entries, list):
        for entry in entries:
            if isinstance(entry, dict) and entry.get("suite_id") == suite_id:
                return entry
    raise ValueError(f"{REGISTRY_PATH}: unknown suite_id {suite_id}")


def _active_suite_paths(repo_root: Path, errors: list[str]) -> set[str]:
    active: set[str] = set()
    suite_root = repo_root / "evals/suites"
    for path in sorted(suite_root.glob("*.json")):
        relative = path.relative_to(repo_root).as_posix()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{relative}: unable to inspect suite: {exc}")
            continue
        if not isinstance(payload, dict):
            continue
        schema = payload.get("schema")
        suite_id = payload.get("suite_id")
        if (
            isinstance(schema, str)
            and schema.startswith("aoa_course_")
            and schema.endswith("_eval_suite_v1")
            and isinstance(suite_id, str)
        ):
            active.add(relative)
    return active

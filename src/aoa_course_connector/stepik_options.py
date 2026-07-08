"""Shared Stepik enrichment option normalization."""

from __future__ import annotations


DEFAULT_MAX_STEP_SOURCES = 10
DEFAULT_STEP_SOURCE_TIMEOUT = 5.0
_MISSING = object()


def normalize_max_step_sources(
    value: object = _MISSING,
    *,
    default: int | None = DEFAULT_MAX_STEP_SOURCES,
) -> int | None:
    """Return a non-negative step-source limit, or None for all steps."""

    if value is _MISSING:
        return default
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("expected a non-negative integer or 'all'")
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        if text.casefold() == "all":
            return None
        try:
            parsed = int(text)
        except ValueError as exc:
            raise ValueError("expected a non-negative integer or 'all'") from exc
    elif isinstance(value, int):
        parsed = value
    else:
        raise ValueError("expected a non-negative integer or 'all'")
    if parsed < 0:
        raise ValueError("expected a non-negative integer or 'all'")
    return parsed


def max_step_sources_packet(value: int | None) -> int | str:
    return "all" if value is None else int(value)


def max_step_sources_token(value: int | None) -> str:
    return str(max_step_sources_packet(value))


def normalize_step_source_timeout(
    value: object = None,
    *,
    default: float = DEFAULT_STEP_SOURCE_TIMEOUT,
) -> float:
    if value is None:
        return default
    if isinstance(value, bool):
        raise ValueError("expected a positive timeout")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("expected a positive timeout") from exc
    if parsed <= 0:
        raise ValueError("expected a positive timeout")
    return parsed

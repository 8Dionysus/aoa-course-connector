"""Storage root helpers."""

from __future__ import annotations

import re
from pathlib import Path

from aoa_course_connector.config import StorageRoots


RUNTIME_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$")
RUNTIME_ID_HELP = "use 1-160 letters, digits, dots, underscores, or hyphens; start with a letter or digit"


def create_storage_roots(roots: StorageRoots) -> list[str]:
    created: list[str] = []
    for path in [roots.data, roots.cache, roots.auth, roots.artifact]:
        existed = path.exists()
        path.mkdir(parents=True, exist_ok=True)
        if not existed:
            created.append(str(path))
    return created


def storage_status(repo_root: Path, roots: StorageRoots, measure: bool = False) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema": "aoa_course_storage_status_v1",
        "repo_root": str(repo_root),
        "mode": roots.mode,
        "roots": roots.as_dict(),
        "exists": {
            "data": roots.data.exists(),
            "cache": roots.cache.exists(),
            "auth": roots.auth.exists(),
            "artifact": roots.artifact.exists(),
        },
        "git_private": True,
    }
    if measure:
        payload["bytes"] = {
            "data": _dir_size(roots.data),
            "cache": _dir_size(roots.cache),
            "auth": _dir_size(roots.auth),
            "artifact": _dir_size(roots.artifact),
        }
    return payload


def run_data_dir(roots: StorageRoots, run_id: str) -> Path:
    return roots.data / "runs" / safe_runtime_id(run_id, field="run_id")


def run_artifact_dir(roots: StorageRoots, run_id: str) -> Path:
    return roots.artifact / "runs" / safe_runtime_id(run_id, field="run_id")


def discovery_data_dir(roots: StorageRoots, run_id: str) -> Path:
    return roots.data / "discovery" / safe_runtime_id(run_id, field="run_id")


def sync_data_dir(roots: StorageRoots, sync_run_id: str) -> Path:
    return roots.data / "sync" / safe_runtime_id(sync_run_id, field="sync_run_id")


def safe_runtime_id(value: object, *, field: str = "runtime_id") -> str:
    text = str(value or "").strip()
    if not RUNTIME_ID_RE.fullmatch(text):
        raise ValueError(f"{field} must be a portable runtime id ({RUNTIME_ID_HELP}): {value!r}")
    return text


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())

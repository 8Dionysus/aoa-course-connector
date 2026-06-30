"""Storage root helpers."""

from __future__ import annotations

from pathlib import Path

from aoa_course_connector.config import StorageRoots


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
    return roots.data / "runs" / run_id


def run_artifact_dir(roots: StorageRoots, run_id: str) -> Path:
    return roots.artifact / "runs" / run_id


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())

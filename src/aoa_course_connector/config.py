"""Repository and environment configuration helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ENV_DATA_ROOT = "AOA_COURSE_DATA_ROOT"
ENV_CACHE_ROOT = "AOA_COURSE_CACHE_ROOT"
ENV_AUTH_ROOT = "AOA_COURSE_AUTH_ROOT"
ENV_ARTIFACT_ROOT = "AOA_COURSE_ARTIFACT_ROOT"
ENV_FAMILY_ROOT = "AOA_COURSE_FAMILY_ROOT"
ENV_INSTANCE_ROOT = "AOA_COURSE_INSTANCE_ROOT"
LOCAL_STATE_DIR = ".connector-state"


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "pyproject.toml").exists() and (candidate / "connector").is_dir():
            return candidate
    return current


@dataclass(frozen=True)
class StorageRoots:
    data: Path
    cache: Path
    auth: Path
    artifact: Path
    mode: str = "environment"

    @classmethod
    def from_env(cls, repo_root: Path | None = None) -> "StorageRoots":
        root = (repo_root or find_repo_root()).resolve()
        names = [ENV_DATA_ROOT, ENV_CACHE_ROOT, ENV_AUTH_ROOT, ENV_ARTIFACT_ROOT]
        if any(os.environ.get(name) for name in names):
            state_root = root / LOCAL_STATE_DIR
            return cls(
                data=_env_path(ENV_DATA_ROOT, root) or state_root / "data",
                cache=_env_path(ENV_CACHE_ROOT, root) or state_root / "cache",
                auth=_env_path(ENV_AUTH_ROOT, root) or state_root / "auth",
                artifact=_env_path(ENV_ARTIFACT_ROOT, root) or state_root / "artifacts",
                mode="environment",
            )
        instance_root = _env_path(ENV_INSTANCE_ROOT, root)
        if instance_root:
            return cls(
                data=instance_root / "data",
                cache=instance_root / "cache",
                auth=instance_root / "auth",
                artifact=instance_root / "artifacts",
                mode="environment_instance_root",
            )
        family_root = _env_path(ENV_FAMILY_ROOT, root)
        if family_root:
            instance = family_root / root.name
            return cls(
                data=instance / "data",
                cache=instance / "cache",
                auth=instance / "auth",
                artifact=instance / "artifacts",
                mode="environment_family_root",
            )
        state_root = root / LOCAL_STATE_DIR
        return cls(
            data=state_root / "data",
            cache=state_root / "cache",
            auth=state_root / "auth",
            artifact=state_root / "artifacts",
            mode="repo_local_default",
        )

    def as_dict(self) -> dict[str, str]:
        return {
            ENV_DATA_ROOT: str(self.data),
            ENV_CACHE_ROOT: str(self.cache),
            ENV_AUTH_ROOT: str(self.auth),
            ENV_ARTIFACT_ROOT: str(self.artifact),
        }


def _env_path(name: str, repo_root: Path) -> Path | None:
    value = os.environ.get(name)
    if not value:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()

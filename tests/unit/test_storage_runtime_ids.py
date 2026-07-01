from __future__ import annotations

from pathlib import Path

import pytest

from aoa_course_connector.config import StorageRoots
from aoa_course_connector.storage import discovery_data_dir, run_artifact_dir, run_data_dir, safe_runtime_id, sync_data_dir


def roots(tmp_path: Path) -> StorageRoots:
    return StorageRoots(
        data=tmp_path / "data",
        cache=tmp_path / "cache",
        auth=tmp_path / "auth",
        artifact=tmp_path / "artifacts",
        mode="test",
    )


def test_runtime_id_allows_portable_slugs(tmp_path: Path) -> None:
    storage = roots(tmp_path)

    assert safe_runtime_id("starter-fixture.v1_2026") == "starter-fixture.v1_2026"
    assert run_data_dir(storage, "starter-fixture") == tmp_path / "data" / "runs" / "starter-fixture"
    assert run_artifact_dir(storage, "starter-fixture") == tmp_path / "artifacts" / "runs" / "starter-fixture"
    assert discovery_data_dir(storage, "browser-discovery") == tmp_path / "data" / "discovery" / "browser-discovery"
    assert sync_data_dir(storage, "browser-sync") == tmp_path / "data" / "sync" / "browser-sync"


@pytest.mark.parametrize(
    "runtime_id",
    [
        "",
        ".hidden",
        "-dash-prefix",
        "../escape",
        "nested/path",
        "nested\\path",
        "/absolute",
        "with space",
        "source:getcourse:fixture",
    ],
)
def test_runtime_id_rejects_path_like_or_nonportable_values(runtime_id: str) -> None:
    with pytest.raises(ValueError, match="portable runtime id"):
        safe_runtime_id(runtime_id, field="run_id")

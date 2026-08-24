from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROVIDER_REF = "f46f146cc79a26fa81ad0f400b9c5774df293e57"
ACTION_REF = "6a79e62c7d20b6b11406dee78f409ada4a51bb3f"


def test_kag_provider_and_workflow_action_are_exact_separate_identities() -> None:
    manifest = json.loads(
        (ROOT / "release" / "release-manifest.json").read_text(encoding="utf-8")
    )
    workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")

    providers = {item["repository"]: item for item in manifest["provider_prerequisites"]}
    provider = providers["8Dionysus/aoa-kag"]
    action = manifest["workflow_pins"]["aoa_kag_repo_local_action"]

    assert provider["tag"] == "v0.5.0"
    assert provider["commit"] == PROVIDER_REF
    assert action["ref"] == ACTION_REF
    assert "action" in action["role"].lower()
    assert PROVIDER_REF != ACTION_REF
    assert f"repo-local-kag-index@{ACTION_REF}" in workflow
    assert PROVIDER_REF not in workflow.split("repo-local-kag-index@", 1)[1].splitlines()[0]

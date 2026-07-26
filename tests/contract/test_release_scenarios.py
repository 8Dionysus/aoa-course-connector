from __future__ import annotations

import importlib.util
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT = Path("scripts/run_release_scenarios.py")


def load_runner():
    spec = importlib.util.spec_from_file_location("run_release_scenarios", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_current_plan_keeps_43_unique_offline_scenarios() -> None:
    runner = load_runner()
    scenarios = runner.build_scenarios()

    assert runner.working_browser_platforms() == ("getcourse", "skillspace")
    assert len(scenarios) == 43
    assert len({item.id for item in scenarios}) == 43
    assert len({item.argv for item in scenarios}) == 43
    assert sum(not item.platform for item in scenarios) == 25
    assert scenarios[-1].id == "install:verify-agent-route"


def test_only_new_qualifying_browser_adapter_gets_nine_scenarios() -> None:
    runner = load_runner()
    adapters = deepcopy(runner.ADAPTERS)
    adapters["new-browser"] = {
        "platform": "new-browser",
        "status": "working_browser_session_discovery_and_crawl_adapter",
        "auth_modes": ["browser_session"],
        "coverage": ["account_discovery", "course_tree", "lesson_page"],
    }
    adapters["future-browser"] = {
        "platform": "future-browser",
        "status": "future_platform_adapter",
        "auth_modes": ["browser_session"],
        "coverage": ["account_discovery", "course_tree", "lesson_page"],
    }

    scenarios = runner.build_scenarios(adapters)

    assert sum(item.platform == "new-browser" for item in scenarios) == 9
    assert not any(item.platform == "future-browser" for item in scenarios)


def test_missing_browser_member_is_rejected() -> None:
    runner = load_runner()
    scenarios = tuple(
        item
        for item in runner.build_scenarios()
        if item.id != "browser:getcourse:crawl:build-graph"
    )

    with pytest.raises(runner.ScenarioPlanError, match="missing browser scenarios"):
        runner.validate_scenario_plan(
            scenarios,
            runner.working_browser_platforms(),
        )


def test_network_permission_escape_is_rejected() -> None:
    runner = load_runner()
    scenarios = list(runner.build_scenarios())
    scenarios[0] = replace(
        scenarios[0],
        argv=(*scenarios[0].argv, "--allow-network"),
    )

    with pytest.raises(runner.ScenarioPlanError, match="denied offline arguments"):
        runner.validate_scenario_plan(
            tuple(scenarios),
            runner.working_browser_platforms(),
        )


def test_install_failure_keeps_named_receipt_and_exit_code(capsys) -> None:
    runner = load_runner()
    install = runner.build_scenarios()[-1]

    def fail_install(*_args, **_kwargs):
        return SimpleNamespace(returncode=17)

    assert runner.execute_scenarios((install,), runner=fail_install) == 17
    captured = capsys.readouterr()
    assert '"id": "install:verify-agent-route"' in captured.err
    assert '"status": "failed"' in captured.err
    assert '"exit_code": 17' in captured.err

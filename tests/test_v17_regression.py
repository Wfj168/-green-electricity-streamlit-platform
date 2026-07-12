from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.model_adapter import run_quick_trial


GOLDEN_PATH = Path(__file__).parent / "golden" / "v17_quick_trials.json"


@pytest.mark.parametrize("scenario_key", ["S0", "S4", "S8"])
def test_v17_quick_trial_matches_golden_baseline(scenario_key: str) -> None:
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    expected = golden["scenarios"][scenario_key]
    trial = run_quick_trial(
        scenario_key,
        n_steps_per_hour=golden["n_steps_per_hour"],
        seed=golden["seed"],
    )

    assert trial["success"] is True, trial["message"]
    result = trial["result"]
    metrics = result["metrics"].set_index("Metric")["Value"].to_dict()
    capacity = result["capacity"].set_index("Technology")["Capacity"].to_dict()

    for name, value in expected["metrics"].items():
        assert metrics[name] == pytest.approx(value, rel=1e-5, abs=1e-6), name
    for technology, value in expected["capacity"].items():
        assert capacity[technology] == pytest.approx(value, rel=1e-5, abs=1e-6), technology

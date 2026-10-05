"""Sanity checks on how the engine ranks fixture ads (relative honesty, not absolute numbers)."""

from __future__ import annotations

import pytest

from engine.simulation.calibration.run_calibration import run_fixtures


@pytest.fixture(scope="module")
def rows():  # noqa: ANN201
    return {r["name"]: r for r in run_fixtures(runs=8, agents=3000, platform="facebook")}


def test_worst_ad_scores_lowest_group(rows) -> None:  # noqa: ANN001
    assert rows["blank_bad"]["score"] < rows["average"]["score"] < rows["strong_all"]["score"]


def test_better_hook_never_lowers_score(rows) -> None:  # noqa: ANN001
    assert rows["strong_all"]["score"] >= rows["strong_image"]["score"] - 1.0
    assert rows["good_not_great"]["score"] >= rows["weak_hook_clear"]["score"] - 1.0


def test_pretty_but_unclear_is_not_strong(rows) -> None:  # noqa: ANN001
    assert rows["unclear_pretty"]["score"] < rows["strong_image"]["score"]

def test_generic_ad_loses_to_surprising_ad_with_same_hook(rows) -> None:  # noqa: ANN001
    assert rows["fresh_surprising"]["score"] - rows["generic_poster"]["score"] >= 8

@pytest.mark.xfail(reason="baseline: engine saturates; target after calibration", strict=False)
def test_spread_between_bad_and_strong(rows) -> None:  # noqa: ANN001
    low = [r["score"] for r in rows.values() if r["expect"] == "low"]
    high = [r["score"] for r in rows.values() if r["expect"] == "high"]
    assert sum(high) / len(high) - sum(low) / len(low) >= 30


@pytest.mark.xfail(reason="baseline: engine rates far above benchmarks; target after calibration", strict=False)
def test_bad_ad_is_not_above_80(rows) -> None:  # noqa: ANN001
    assert rows["boring_stock"]["score"] < 60
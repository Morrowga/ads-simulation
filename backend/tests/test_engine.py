"""Engine tests: determinism with fixed seeds and sanity checks."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from engine.simulation.results.aggregate import aggregate_runs, should_stop
from engine.cli import config_from_sample
from engine.data_loader import load_all
from engine.simulation.results.evidence import EvidenceBuilder, build_evidence, validate_reasons
from engine.simulation.runtime.montecarlo import simulate_run
from engine.simulation.pipeline import build_population_and_archetypes, priors_for_all_scenarios
from engine.simulation.results.scoring import DEFAULT_SCORE_WEIGHTS, score_run
from engine.simulation.config.resolver import resolve
from engine.simulation.types import AdFeatures

SAMPLE = json.loads((Path(__file__).resolve().parent.parent / "samples" / "sample_test.json").read_text())
DATA = load_all()


def _setup(sample: dict, agents: int = 4000, platform: str = "facebook"):  # noqa: ANN202
    cfg = config_from_sample(sample, DATA, runs=10, agents=agents)
    ad = AdFeatures.from_dict(sample["ad_features"])
    pop, table = build_population_and_archetypes(cfg, platform, 0)
    priors = priors_for_all_scenarios(table, ad, cfg, platform)
    return cfg, ad, pop, priors


def _run(cfg, ad, pop, priors, seed: int = 7, share: float = 60.0):  # noqa: ANN001, ANN202
    sc = cfg.scenarios[0]
    return simulate_run(pop, ad, priors[sc.code], cfg, "facebook", sc, seed=seed, budget_share=share)


def test_deterministic_with_fixed_seed() -> None:
    cfg, ad, pop, priors = _setup(SAMPLE)
    a = _run(cfg, ad, pop, priors, seed=123)
    b = _run(cfg, ad, pop, priors, seed=123)
    assert a["counts"] == b["counts"] and a["rates"] == b["rates"]
    c = _run(cfg, ad, pop, priors, seed=124)
    assert c["counts"] != a["counts"]


def test_more_budget_more_reach() -> None:
    low = copy.deepcopy(SAMPLE)
    low["test"]["budget_usd"] = 20.0
    high = copy.deepcopy(SAMPLE)
    high["test"]["budget_usd"] = 120.0
    cfg_l, ad, pop_l, pr_l = _setup(low)
    cfg_h, _, pop_h, pr_h = _setup(high)
    seen_l = np.mean([_run(cfg_l, ad, pop_l, pr_l, seed=s)["counts"]["seen"] for s in range(3)])
    seen_h = np.mean([_run(cfg_h, ad, pop_h, pr_h, seed=s)["counts"]["seen"] for s in range(3)])
    assert seen_h > seen_l * 2


def test_organic_reach_grows_with_followers_and_is_tiny_for_new_brand() -> None:
    def organic(followers: int) -> float:
        s = copy.deepcopy(SAMPLE)
        s["test"]["post_type"] = "organic"
        s["test"]["goal"] = "engagement"
        s["test"]["budget_usd"] = None
        s["test"]["schedule"] = {"post_at": "2026-10-03T18:00:00", "observe_days": 3}
        s["profile"]["data"]["followers"] = followers
        cfg, ad, pop, priors = _setup(s, agents=6000)
        return float(np.mean([_run(cfg, ad, pop, priors, seed=i)["counts"]["seen"] for i in range(3)]))

    new_brand = organic(20)
    mid = organic(3000)
    big = organic(30000)
    assert new_brand < 40, new_brand  # a new brand with 20 followers reaches almost nobody
    assert mid > new_brand and big > mid


def test_organic_reach_decays_over_time() -> None:
    s = copy.deepcopy(SAMPLE)
    s["test"]["post_type"] = "organic"
    s["test"]["goal"] = "engagement"
    s["test"]["budget_usd"] = None
    s["test"]["schedule"] = {"post_at": "2026-10-03T18:00:00", "observe_days": 3}
    s["profile"]["data"]["followers"] = 40000
    cfg, ad, pop, priors = _setup(s, agents=8000)
    m = _run(cfg, ad, pop, priors, seed=3)
    hourly = np.array(m["timing"]["hourly_seen"], dtype=float)
    first_day, last_day = hourly[:24].sum(), hourly[48:72].sum()
    assert first_day > last_day * 2, (first_day, last_day)


def test_later_offer_fewer_clicks_from_impatient_agents() -> None:
    early = copy.deepcopy(SAMPLE)
    early["ad_features"]["offer_visible_at_s"] = 1.0
    late = copy.deepcopy(SAMPLE)
    late["ad_features"]["offer_visible_at_s"] = 9.0
    cfg, _, pop, _ = _setup(early, agents=8000)
    ad_e, ad_l = AdFeatures.from_dict(early["ad_features"]), AdFeatures.from_dict(late["ad_features"])
    _, table = build_population_and_archetypes(cfg, "facebook", 0)
    pr_e = priors_for_all_scenarios(table, ad_e, cfg, "facebook")
    pr_l = priors_for_all_scenarios(table, ad_l, cfg, "facebook")
    imp_e = np.mean([_run(cfg, ad_e, pop, pr_e, seed=i)["dropoff"]["impatient_ctr"] for i in range(4)])
    imp_l = np.mean([_run(cfg, ad_l, pop, pr_l, seed=i)["dropoff"]["impatient_ctr"] for i in range(4)])
    assert imp_l < imp_e, (imp_e, imp_l)
    late_share = np.mean(
        [_run(cfg, ad_l, pop, pr_l, seed=i)["dropoff"]["impatient_left_share"] for i in range(4)]
    )
    assert late_share > 0.5


def test_fatigue_grows_with_exposures() -> None:
    s = copy.deepcopy(SAMPLE)
    s["test"]["budget_usd"] = 400.0  # enough budget for repeat exposures
    cfg, ad, pop, priors = _setup(s, agents=6000)
    m = _run(cfg, ad, pop, priors, seed=11)
    rates = m["fatigue"]["stop_rate_by_exposure"]
    assert m["fatigue"]["seen_by_exposure"][1] > 50
    assert rates[0] > rates[1] > 0, rates


def test_goal_based_score_weights() -> None:
    metrics = {
        "rates": {
            "stop_rate": 0.14,
            "ctr": 0.012,
            "buy_rate": 0.0026,
            "message_rate": 0.001,
            "engagement_rate": 0.045,
            "reach_rate": 0.1,
        },
        "sentiment": 0.1,
    }
    bench = {
        "stop_rate": 0.14,
        "ctr": 0.012,
        "buy_rate": 0.0026,
        "message_rate": 0.008,
        "engagement_rate": 0.045,
        "cvr": 0.02,
    }
    sales = score_run(metrics, "sales", bench, DEFAULT_SCORE_WEIGHTS)
    messages = score_run(metrics, "messages", bench, DEFAULT_SCORE_WEIGHTS)
    assert sales > messages  # the message rate is far below benchmark, buys are on benchmark
    custom = {"sales": {"goal_rate": 1.0}}
    assert score_run(metrics, "sales", bench, custom) == 50.0  # exactly on benchmark -> 0.5 * 100


def test_stopping_rule_and_aggregate() -> None:
    cfg, ad, pop, priors = _setup(SAMPLE, agents=3000)
    runs = [_run(cfg, ad, pop, priors, seed=i) for i in range(12)]
    for r in runs:
        r["score"] = score_run(
            r, cfg.test.goal, cfg.platforms["facebook"].benchmarks, cfg.weights.score_by_goal
        )
    assert not should_stop(runs[:5], min_runs=10)
    agg = aggregate_runs(runs, "messages")
    assert agg["runs"] == 12 and agg["goal_metric"] == "messages"
    assert (
        agg["rates"]["stop_rate"]["p10"]
        <= agg["rates"]["stop_rate"]["p50"]
        <= agg["rates"]["stop_rate"]["p90"]
    )
    assert "language_group" in agg["segments"] and "th" in agg["segments"]["language_group"]


def test_settings_layering_overrides() -> None:
    data = copy.deepcopy(DATA)
    test = dict(SAMPLE["test"])
    country = data["countries"]["TH"]
    country_row = {"code": "TH", "name": "Thailand", "currency": "THB", "version": 1, "data": country["data"]}
    # platform market benchmark overrides the country benchmark; category multiplies it
    cfg = resolve(
        country=country_row,
        platforms={"facebook": data["platforms"]["facebook"]},
        category=data["categories"]["restaurant"],
        scenarios=data["scenarios"],
        weights=data["weights"],
        test={**test, "platforms": [{"code": "facebook", "placements": ["feed"], "budget_share": 100}]},
        tier=data["tiers"]["standard"],
        profile={},
    )
    fb = cfg.platforms["facebook"]
    market_ctr = data["platforms"]["facebook"]["markets"]["TH"]["benchmarks"]["ctr"]
    assert fb.benchmarks["ctr"] == pytest.approx(
        market_ctr * data["categories"]["restaurant"]["benchmark_adjustments"]["ctr"]
    )
    # MM country override of the category applies
    mm_row = {
        "code": "MM",
        "name": "Myanmar",
        "currency": "MMK",
        "version": 1,
        "data": data["countries"]["MM"]["data"],
    }
    cfg_mm = resolve(
        country=mm_row,
        platforms={"facebook": data["platforms"]["facebook"]},
        category=data["categories"]["restaurant"],
        scenarios=data["scenarios"],
        weights=data["weights"],
        test={
            **test,
            "country_code": "MM",
            "platforms": [{"code": "facebook", "placements": ["feed"], "budget_share": 100}],
        },
        tier=data["tiers"]["standard"],
        profile={},
    )
    assert cfg_mm.category.benchmark_adjustments["message_rate"] == 2.0
    assert cfg_mm.versions["country"] == {"code": "MM", "version": 1}
    # scenario selection: April in Thailand includes Songkran
    cfg_apr = resolve(
        country=country_row,
        platforms={"facebook": data["platforms"]["facebook"]},
        category=data["categories"]["restaurant"],
        scenarios=data["scenarios"],
        weights=data["weights"],
        test={
            **test,
            "schedule": {"start_date": "2027-04-12", "days": 3},
            "platforms": [{"code": "facebook", "placements": ["feed"], "budget_share": 100}],
        },
        tier=data["tiers"]["standard"],
        profile={},
    )
    assert "songkran_th" in [s.code for s in cfg_apr.scenarios] and "thingyan_mm" not in [
        s.code for s in cfg_apr.scenarios
    ]
    assert cfg_apr.scenarios[0].code == "normal"


def test_evidence_and_reason_validation() -> None:
    cfg, ad, pop, priors = _setup(SAMPLE, agents=3000)
    runs = [_run(cfg, ad, pop, priors, seed=i) for i in range(6)]
    for r in runs:
        r["score"] = 50.0
    agg = aggregate_runs(runs, "messages")
    evidence = build_evidence(
        agg, priors[cfg.scenarios[0].code], cfg, "facebook", 0, ad.to_dict(), EvidenceBuilder()
    )
    ids = {e["id"] for e in evidence}
    assert "E1" in ids and any(e["type"] == "dropoff" for e in evidence)
    stop = agg["rates"]["stop_rate"]["p50"]
    good = {
        "section": "attention",
        "statement": f"The stop rate on facebook was {stop * 100:.1f}%.",
        "evidence_ids": ["E1"],
        "confidence": 0.8,
    }
    advice = {
        "section": "attention",
        "statement": "You should add a price to the image.",
        "evidence_ids": ["E1"],
        "confidence": 0.8,
    }
    no_ev = {"section": "attention", "statement": "People liked it.", "evidence_ids": [], "confidence": 0.5}
    wrong_num = {
        "section": "attention",
        "statement": "Exactly 77.7% of agents bought the product.",
        "evidence_ids": ["E1"],
        "confidence": 0.5,
    }
    accepted, rejected = validate_reasons([good, advice, no_ev, wrong_num], evidence)
    assert [a["statement"] for a in accepted] == [good["statement"]]
    problems = {r["statement"]: r["problems"] for r in rejected}
    assert any("banned_words" in p for p in problems[advice["statement"]])
    assert "no_evidence" in problems[no_ev["statement"]]
    assert "numbers_not_in_evidence" in problems[wrong_num["statement"]]

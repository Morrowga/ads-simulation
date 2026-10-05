"""Vary one ad feature at a time around the 'average' ad and show how the score moves.

python -m engine.simulation.calibration.sweep
"""

from __future__ import annotations

from engine.simulation.calibration.run_calibration import run_fixtures

BASE = {"hook_strength": 0.45, "visual_quality": 0.55, "clarity": 0.55, "offer_visible_at_s": 4.0}
SWEEPS = {
    "hook_strength": [0.1, 0.3, 0.5, 0.7, 0.9],
    "visual_quality": [0.1, 0.3, 0.5, 0.7, 0.9],
    "clarity": [0.1, 0.3, 0.5, 0.7, 0.9],
    "offer_visible_at_s": [0.5, 3.0, 6.0, 10.0, 14.0],
    "novelty": [0.1, 0.3, 0.5, 0.7, 0.9],
    "genericness": [0.1, 0.3, 0.5, 0.7, 0.9]
}


def main() -> None:
    fixtures = [
        {"name": f"{feat}={v}", "expect": "mid", "ad": {**BASE, feat: v}}
        for feat, vals in SWEEPS.items()
        for v in vals
    ]
    rows = run_fixtures(runs=8, agents=4000, platform="facebook", fixtures=fixtures)
    by_name = {r["name"]: r for r in rows}
    for feat, vals in SWEEPS.items():
        print(f"\n{feat}")
        for v in vals:
            r = by_name[f"{feat}={v}"]
            print(f"  {v:>5}  score {r['score']:5.1f}  stop {r['stop']:.3f}  ctr {r['ctr']:.4f}")
        lo, hi = by_name[f"{feat}={vals[0]}"]["score"], by_name[f"{feat}={vals[-1]}"]["score"]
        print(f"  -> swing {hi - lo:+.1f}")


if __name__ == "__main__":
    main()
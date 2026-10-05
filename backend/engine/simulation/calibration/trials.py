"""Try alternative behavior weights side by side (in memory only, nothing is saved).

python -m engine.simulation.calibration.trials
"""

from __future__ import annotations

from engine.simulation.calibration.run_calibration import run_fixtures

TRIALS: dict[str, dict[str, float]] = {
    "C": {"w_hook": 0.8, "w_prior": 1.0, "b0_stop": -2.7},
    "G": {"w_hook": 0.8, "w_prior": 1.0, "b0_stop": -2.7, "b0_buy": -1.6},
}

def main() -> None:
    results = {name: {r["name"]: r for r in run_fixtures(runs=16, agents=4000, platform="facebook", weight_overrides=ov)} for name, ov in TRIALS.items()}
    names = list(next(iter(results.values())).keys())
    print(f"\n{'ad':<18}" + "".join(f"{t:>9}" for t in TRIALS))
    for n in names:
        print(f"{n:<18}" + "".join(f"{results[t][n]['score']:>9.1f}" for t in TRIALS))
    print(f"\n{'avg stop':<18}" + "".join(f"{results[t]['average']['stop']:>9.3f}" for t in TRIALS) + "   (benchmark 0.14)")
    print(f"{'avg ctr':<18}" + "".join(f"{results[t]['average']['ctr']:>9.4f}" for t in TRIALS) + "   (benchmark ~0.013)")
    print(f"{'avg buy':<18}" + "".join(f"{results[t]['average']['buy']:>9.4f}" for t in TRIALS) + "   (benchmark 0.0026)")

if __name__ == "__main__":
    main()